from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from ..hashing import sha256_file


COMPARISON_SCHEMA_VERSION = "0.1"
SOURCE_STATES = {"available", "missing", "layout_inverse_failure", "load_error"}
FAILED_PAIR_STATES = {"shape_mismatch", "dtype_mismatch", "value_mismatch"}


CoordinateExplainer = Callable[[tuple[int, ...]], Mapping[str, Any]]


@dataclass
class LogicalTensorSource:
    """One result after any physical-layout inverse has completed.

    ``coordinate_explainer`` is intentionally a callback rather than a fixed
    hardware layout dependency. A future approved layout can use it to attach
    slice/bank/address provenance to the first logical mismatch without changing
    the comparison algorithm.
    """

    name: str
    array: np.ndarray | None = None
    status: str = "available"
    path: str | None = None
    sha256: str | None = None
    error: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    coordinate_explainer: CoordinateExplainer | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("comparison source name must be non-empty")
        if self.status not in SOURCE_STATES:
            raise ValueError(f"unsupported source status: {self.status}")
        if self.status == "available" and self.array is None:
            raise ValueError(f"available source {self.name} has no logical tensor")
        if self.array is not None and not isinstance(self.array, np.ndarray):
            raise TypeError(f"source {self.name} logical tensor must be a numpy array")

    @classmethod
    def from_array(
        cls,
        name: str,
        array: np.ndarray,
        *,
        provenance: Mapping[str, Any] | None = None,
        coordinate_explainer: CoordinateExplainer | None = None,
    ) -> "LogicalTensorSource":
        return cls(
            name=name,
            array=array,
            provenance=dict(provenance or {}),
            coordinate_explainer=coordinate_explainer,
        )


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _require_nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value.strip()


def _validate_tolerance(value: Any, location: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a finite non-negative number or null")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{location} must be a finite non-negative number or null")
    return result


def load_comparison_request(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"comparison request is not valid JSON: {path}") from error
    return _require_object(value, "comparison request")


def _load_source(
    name: str,
    raw_spec: Any,
    base_dir: Path,
) -> LogicalTensorSource:
    spec = _require_object(raw_spec, f"sources.{name}")
    allowed = {"status", "path", "error", "provenance"}
    unexpected = sorted(set(spec) - allowed)
    if unexpected:
        raise ValueError(f"sources.{name} contains unexpected fields: {unexpected}")
    status = spec.get("status", "available")
    if status not in {"available", "missing", "layout_inverse_failure"}:
        raise ValueError(f"sources.{name}.status is unsupported: {status}")
    raw_path = spec.get("path")
    if raw_path is not None:
        raw_path = _require_nonempty_string(raw_path, f"sources.{name}.path")
    error = spec.get("error")
    if error is not None:
        error = _require_nonempty_string(error, f"sources.{name}.error")
    provenance = spec.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError(f"sources.{name}.provenance must be an object")

    if status != "available":
        return LogicalTensorSource(
            name=name,
            status=status,
            path=raw_path,
            error=error or status.replace("_", " "),
            provenance=dict(provenance),
        )
    if raw_path is None:
        return LogicalTensorSource(
            name=name,
            status="missing",
            error="available source did not declare a logical .npy path",
            provenance=dict(provenance),
        )

    source_path = Path(raw_path)
    if not source_path.is_absolute():
        source_path = base_dir / source_path
    source_path = source_path.resolve()
    if not source_path.is_file():
        return LogicalTensorSource(
            name=name,
            status="missing",
            path=raw_path,
            error=f"logical tensor file does not exist: {source_path}",
            provenance=dict(provenance),
        )
    try:
        array = np.load(source_path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error_value:
        return LogicalTensorSource(
            name=name,
            status="load_error",
            path=raw_path,
            sha256=sha256_file(source_path),
            error=str(error_value),
            provenance=dict(provenance),
        )
    if not isinstance(array, np.ndarray):
        if hasattr(array, "close"):
            array.close()
        return LogicalTensorSource(
            name=name,
            status="load_error",
            path=raw_path,
            sha256=sha256_file(source_path),
            error="logical tensor source must be a single .npy array, not an archive",
            provenance=dict(provenance),
        )
    return LogicalTensorSource(
        name=name,
        array=array,
        path=raw_path,
        sha256=sha256_file(source_path),
        provenance=dict(provenance),
    )


def _json_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, complex):
        return {"real": _json_scalar(value.real), "imag": _json_scalar(value.imag)}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _source_summary(source: LogicalTensorSource) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": source.status,
        "path": source.path,
        "sha256": source.sha256,
        "error": source.error,
        "provenance": dict(source.provenance),
        "shape": None,
        "dtype": None,
        "element_count": None,
        "logical_nbytes": None,
    }
    if source.array is not None:
        result.update(
            {
                "shape": list(source.array.shape),
                "dtype": str(source.array.dtype),
                "element_count": int(source.array.size),
                "logical_nbytes": int(source.array.nbytes),
            }
        )
    return result


def _coordinate_provenance(
    source: LogicalTensorSource, coordinate: tuple[int, ...]
) -> dict[str, Any]:
    result = dict(source.provenance)
    result["logical_coordinate"] = list(coordinate)
    if source.coordinate_explainer is not None:
        explained = source.coordinate_explainer(coordinate)
        if not isinstance(explained, Mapping):
            raise TypeError(
                f"coordinate explainer for {source.name} must return a mapping"
            )
        result.update(dict(explained))
    return result


def _blocked_pair(
    left: LogicalTensorSource,
    right: LogicalTensorSource,
) -> dict[str, Any] | None:
    blocked = [item for item in (left, right) if item.status != "available"]
    if not blocked:
        return None
    priority = {
        "layout_inverse_failure": 0,
        "load_error": 1,
        "missing": 2,
    }
    status = min((item.status for item in blocked), key=lambda item: priority[item])
    return {
        "left": left.name,
        "right": right.name,
        "status": status,
        "passed": False,
        "comparison_mode": None,
        "element_count": None,
        "mismatch_count": None,
        "max_absolute_error": None,
        "max_relative_error": None,
        "first_mismatch": None,
        "blocked_sources": [
            {"name": item.name, "status": item.status, "error": item.error}
            for item in blocked
        ],
    }


def _compare_pair(
    left: LogicalTensorSource,
    right: LogicalTensorSource,
    *,
    atol: float | None,
    rtol: float | None,
    block_elements: int,
) -> dict[str, Any]:
    blocked = _blocked_pair(left, right)
    if blocked is not None:
        return blocked
    assert left.array is not None and right.array is not None

    base = {
        "left": left.name,
        "right": right.name,
        "passed": False,
        "element_count": None,
        "mismatch_count": None,
        "max_absolute_error": None,
        "max_relative_error": None,
        "first_mismatch": None,
        "blocked_sources": [],
    }
    if left.array.shape != right.array.shape:
        return {
            **base,
            "status": "shape_mismatch",
            "comparison_mode": None,
            "left_shape": list(left.array.shape),
            "right_shape": list(right.array.shape),
        }
    if left.array.dtype != right.array.dtype:
        return {
            **base,
            "status": "dtype_mismatch",
            "comparison_mode": None,
            "left_dtype": str(left.array.dtype),
            "right_dtype": str(right.array.dtype),
        }

    kind = left.array.dtype.kind
    if kind in {"b", "i", "u"}:
        comparison_mode = "bit_exact"
    elif kind in {"f", "c"}:
        comparison_mode = "tolerance"
        if atol is None or rtol is None:
            return {
                **base,
                "status": "tolerance_required",
                "comparison_mode": comparison_mode,
            }
    else:
        return {
            **base,
            "status": "unsupported_dtype",
            "comparison_mode": None,
            "dtype": str(left.array.dtype),
        }

    element_count = int(left.array.size)
    mismatch_count = 0
    first_flat_index: int | None = None
    first_values: dict[str, Any] | None = None
    max_absolute_error = 0.0 if comparison_mode == "tolerance" else None
    max_relative_error = 0.0 if comparison_mode == "tolerance" else None

    for start in range(0, element_count, block_elements):
        stop = min(start + block_elements, element_count)
        left_block = np.asarray(left.array.flat[start:stop])
        right_block = np.asarray(right.array.flat[start:stop])
        if comparison_mode == "bit_exact":
            equal = left_block == right_block
        else:
            # The left side is the reference for each ordered pair, so pass it
            # as numpy.isclose's second (reference) operand for the rtol term.
            equal = np.isclose(
                right_block,
                left_block,
                atol=atol,
                rtol=rtol,
                equal_nan=True,
            )
            working_dtype = np.complex128 if kind == "c" else np.float64
            left_work = left_block.astype(working_dtype, copy=False)
            right_work = right_block.astype(working_dtype, copy=False)
            absolute = np.abs(left_work - right_work)
            finite_absolute = absolute[~np.isnan(absolute)]
            if finite_absolute.size:
                block_absolute = float(np.max(finite_absolute))
                if not math.isnan(block_absolute):
                    max_absolute_error = max(max_absolute_error or 0.0, block_absolute)
                denominator = np.abs(left_work)
                relative = np.zeros_like(absolute, dtype=np.float64)
                np.divide(
                    absolute,
                    denominator,
                    out=relative,
                    where=denominator != 0,
                )
                relative[(denominator == 0) & (absolute != 0)] = np.inf
                finite_relative = relative[~np.isnan(relative)]
                block_relative = (
                    float(np.max(finite_relative)) if finite_relative.size else 0.0
                )
                if not math.isnan(block_relative):
                    max_relative_error = max(max_relative_error or 0.0, block_relative)

        block_mismatch_count = int(np.count_nonzero(~equal))
        mismatch_count += block_mismatch_count
        if block_mismatch_count and first_flat_index is None:
            first_in_block = int(np.flatnonzero(~equal)[0])
            first_flat_index = start + first_in_block
            first_values = {
                left.name: _json_scalar(left_block[first_in_block]),
                right.name: _json_scalar(right_block[first_in_block]),
            }

    first_mismatch = None
    if first_flat_index is not None:
        coordinate = tuple(
            int(item) for item in np.unravel_index(first_flat_index, left.array.shape)
        )
        first_mismatch = {
            "flat_index": first_flat_index,
            "logical_coordinate": list(coordinate),
            "values": first_values,
            "provenance": {
                left.name: _coordinate_provenance(left, coordinate),
                right.name: _coordinate_provenance(right, coordinate),
            },
        }

    passed = mismatch_count == 0
    return {
        **base,
        "status": "passed" if passed else "value_mismatch",
        "passed": passed,
        "comparison_mode": comparison_mode,
        "element_count": element_count,
        "mismatch_count": mismatch_count,
        "max_absolute_error": _json_scalar(max_absolute_error),
        "max_relative_error": _json_scalar(max_relative_error),
        "first_mismatch": first_mismatch,
    }


def compare_logical_tensor(
    *,
    tensor_id: str,
    sources: Mapping[str, LogicalTensorSource | np.ndarray],
    required_sources: Sequence[str] = ("golden", "simulator", "hardware"),
    onnx_node_id: str | None = None,
    hw_op_id: str | None = None,
    topology_index: int | None = None,
    atol: float | None = None,
    rtol: float | None = None,
    block_elements: int = 1_048_576,
) -> dict[str, Any]:
    tensor_id = _require_nonempty_string(tensor_id, "tensor_id")
    if len(required_sources) < 2 or len(set(required_sources)) != len(required_sources):
        raise ValueError("required_sources must contain at least two unique names")
    if block_elements <= 0:
        raise ValueError("block_elements must be positive")
    atol = _validate_tolerance(atol, "atol")
    rtol = _validate_tolerance(rtol, "rtol")

    normalized: dict[str, LogicalTensorSource] = {}
    for name in required_sources:
        _require_nonempty_string(name, "required_sources item")
        value = sources.get(name)
        if isinstance(value, np.ndarray):
            normalized[name] = LogicalTensorSource.from_array(name, value)
        elif isinstance(value, LogicalTensorSource):
            if value.name != name:
                raise ValueError(
                    f"source mapping key {name} does not match source name {value.name}"
                )
            normalized[name] = value
        elif value is None:
            normalized[name] = LogicalTensorSource(
                name=name,
                status="missing",
                error="required source was not provided",
            )
        else:
            raise TypeError(f"source {name} must be a numpy array or LogicalTensorSource")

    pairs = [
        _compare_pair(
            normalized[left],
            normalized[right],
            atol=atol,
            rtol=rtol,
            block_elements=block_elements,
        )
        for left, right in itertools.combinations(required_sources, 2)
    ]
    pair_statuses = [item["status"] for item in pairs]
    if all(status == "passed" for status in pair_statuses):
        status = "passed"
    elif any(item in FAILED_PAIR_STATES for item in pair_statuses):
        status = "failed"
    else:
        status = "incomplete"

    first_failed_pair = next((item for item in pairs if not item["passed"]), None)
    first_failure = None
    if first_failed_pair is not None:
        first_failure = {
            "category": first_failed_pair["status"],
            "pair": [first_failed_pair["left"], first_failed_pair["right"]],
            "detail": first_failed_pair.get("first_mismatch"),
            "blocked_sources": first_failed_pair.get("blocked_sources", []),
        }
    return {
        "tensor_id": tensor_id,
        "onnx_node_id": onnx_node_id,
        "hw_op_id": hw_op_id,
        "topology_index": topology_index,
        "status": status,
        "required_sources": list(required_sources),
        "tolerance": {"atol": atol, "rtol": rtol},
        "sources": {name: _source_summary(normalized[name]) for name in required_sources},
        "pairs": pairs,
        "first_failure": first_failure,
    }


def compare_request(
    request: Mapping[str, Any],
    *,
    base_dir: Path,
    block_elements: int = 1_048_576,
) -> dict[str, Any]:
    request = _require_object(dict(request), "comparison request")
    allowed = {"schema_version", "comparison_id", "required_sources", "tensors"}
    unexpected = sorted(set(request) - allowed)
    if unexpected:
        raise ValueError(f"comparison request contains unexpected fields: {unexpected}")
    if request.get("schema_version") != COMPARISON_SCHEMA_VERSION:
        raise ValueError(
            f"comparison request schema_version must be {COMPARISON_SCHEMA_VERSION}"
        )
    comparison_id = _require_nonempty_string(
        request.get("comparison_id"), "comparison_id"
    )
    if "required_sources" not in request:
        raise ValueError("comparison request is missing required_sources")
    required_sources = request["required_sources"]
    if not isinstance(required_sources, list):
        raise ValueError("required_sources must be an array")
    required_sources = [
        _require_nonempty_string(item, "required_sources item")
        for item in required_sources
    ]
    if len(required_sources) < 2 or len(set(required_sources)) != len(required_sources):
        raise ValueError("required_sources must contain at least two unique names")
    raw_tensors = request.get("tensors")
    if not isinstance(raw_tensors, list) or not raw_tensors:
        raise ValueError("tensors must be a non-empty array")

    tensor_requests: list[tuple[int, int, dict[str, Any]]] = []
    seen_tensor_ids: set[str] = set()
    for request_index, raw_tensor in enumerate(raw_tensors):
        tensor = _require_object(raw_tensor, f"tensors[{request_index}]")
        allowed_tensor = {
            "tensor_id",
            "onnx_node_id",
            "hw_op_id",
            "topology_index",
            "atol",
            "rtol",
            "sources",
        }
        unexpected_tensor = sorted(set(tensor) - allowed_tensor)
        if unexpected_tensor:
            raise ValueError(
                f"tensors[{request_index}] contains unexpected fields: {unexpected_tensor}"
            )
        tensor_id = _require_nonempty_string(
            tensor.get("tensor_id"), f"tensors[{request_index}].tensor_id"
        )
        if tensor_id in seen_tensor_ids:
            raise ValueError(f"duplicate tensor_id in comparison request: {tensor_id}")
        seen_tensor_ids.add(tensor_id)
        topology_index = tensor.get("topology_index", request_index)
        if isinstance(topology_index, bool) or not isinstance(topology_index, int):
            raise ValueError(
                f"tensors[{request_index}].topology_index must be an integer"
            )
        for identity_field in ("onnx_node_id", "hw_op_id"):
            identity = tensor.get(identity_field)
            if identity is not None:
                _require_nonempty_string(
                    identity, f"tensors[{request_index}].{identity_field}"
                )
        tensor_requests.append((topology_index, request_index, tensor))

    tensor_reports: list[dict[str, Any]] = []
    for topology_index, _request_index, tensor in sorted(tensor_requests):
        raw_sources = _require_object(tensor.get("sources"), "tensor sources")
        unexpected_sources = sorted(set(raw_sources) - set(required_sources))
        if unexpected_sources:
            raise ValueError(
                f"tensor {tensor['tensor_id']} declares unexpected sources: {unexpected_sources}"
            )
        loaded_sources = {
            name: _load_source(name, raw_sources[name], base_dir)
            if name in raw_sources
            else LogicalTensorSource(
                name=name,
                status="missing",
                error="required source was omitted from the request",
            )
            for name in required_sources
        }
        tensor_reports.append(
            compare_logical_tensor(
                tensor_id=tensor["tensor_id"],
                sources=loaded_sources,
                required_sources=required_sources,
                onnx_node_id=tensor.get("onnx_node_id"),
                hw_op_id=tensor.get("hw_op_id"),
                topology_index=topology_index,
                atol=tensor.get("atol"),
                rtol=tensor.get("rtol"),
                block_elements=block_elements,
            )
        )

    statuses = [item["status"] for item in tensor_reports]
    if all(item == "passed" for item in statuses):
        status = "passed"
    elif any(item == "failed" for item in statuses):
        status = "failed"
    else:
        status = "incomplete"
    first_failure = next(
        (
            {
                "tensor_id": item["tensor_id"],
                "onnx_node_id": item["onnx_node_id"],
                "hw_op_id": item["hw_op_id"],
                "topology_index": item["topology_index"],
                **(item["first_failure"] or {}),
            }
            for item in tensor_reports
            if item["status"] != "passed"
        ),
        None,
    )
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "report_type": "logical_tensor_comparison",
        "comparison_id": comparison_id,
        "status": status,
        "required_sources": list(required_sources),
        "summary": {
            "tensor_count": len(tensor_reports),
            "passed": statuses.count("passed"),
            "failed": statuses.count("failed"),
            "incomplete": statuses.count("incomplete"),
        },
        "first_failure": first_failure,
        "tensors": tensor_reports,
    }
