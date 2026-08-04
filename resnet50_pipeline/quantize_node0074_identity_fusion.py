"""Instance-level Dequantize/View/Quantize identity-fusion proof for node0074.

This module deliberately proves only the frozen ResNet50 chain
node0072 -> node0073 -> node0074.  It does not provide an exact binary32
division primitive and does not generate an NDP target.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path
from typing import Any


SCHEMA = "resnet50-quantize-node0074-dq-view-q-identity-fusion-v1"
REPORT_SCHEMA = f"{SCHEMA}-report"
TEST_ID = "r5-quantize-node0074-dq-view-q-identity-fusion-v1"
SCALE_BITS = "0x3cbf57ec"
SCALE_VALUE_SHA256 = (
    "a0da76078599a1809616c74430a869c573c530c8f89dec21191c963aadb321bc"
)
ZERO_POINT_VALUE_SHA256 = (
    "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d"
)
MODEL_SHA256 = (
    "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"
)
SOURCE_TENSOR_ID = "tensor-ab32f279540568c3"
OLD_DEQUANT_TENSOR_ID = "tensor-50c285690f899b1b"
OLD_VIEW_TENSOR_ID = "tensor-9b1363d3baf474c8"
TARGET_TENSOR_ID = "tensor-6fbd5707d5f08110"
SOURCE_STORAGE_ID = (
    "r5:activation:node-0071:D:tensor-ab32f279540568c3:"
    "batch-slice-sharded-16x2048-v1"
)
ORDERED_ADDRESS_SHA256 = (
    "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
)
WRITTEN_BYTE_SET_SHA256 = (
    "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
)


class IdentityFusionError(ValueError):
    """Raised when an instance-level identity-fusion gate fails closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IdentityFusionError(f"JSON root must be an object: {path}")
    return value


def canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def owner_section_sha256(section: dict[str, Any]) -> str:
    payload = dict(section)
    payload.pop("owner_section_content_sha256", None)
    return canonical_json_sha256(payload)


def bits_to_fraction(bits_text: str) -> Fraction:
    bits = int(bits_text, 16)
    sign = -1 if bits >> 31 else 1
    exponent = (bits >> 23) & 0xFF
    significand = bits & 0x7FFFFF
    if exponent == 0xFF:
        raise IdentityFusionError("non-finite binary32 is outside this proof")
    if exponent == 0:
        if significand == 0:
            return Fraction(0)
        value = Fraction(sign * significand, 1 << 149)
    else:
        significand |= 1 << 23
        power = exponent - 127 - 23
        value = Fraction(sign * significand)
        if power >= 0:
            value *= 1 << power
        else:
            value /= 1 << -power
    return value


def _round_fraction_to_even_integer(value: Fraction) -> int:
    if value < 0:
        return -_round_fraction_to_even_integer(-value)
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return quotient
    if doubled > value.denominator:
        return quotient + 1
    return quotient if quotient % 2 == 0 else quotient + 1


def _floor_log2(value: Fraction) -> int:
    if value <= 0:
        raise IdentityFusionError("floor_log2 requires a positive value")
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    if exponent >= 0:
        if value.numerator < value.denominator * (1 << exponent):
            exponent -= 1
    elif value.numerator * (1 << -exponent) < value.denominator:
        exponent -= 1
    return exponent


def round_fraction_to_binary32_bits(value: Fraction) -> int:
    """Round an exact rational to IEEE-754 binary32, nearest ties-to-even."""

    if value == 0:
        return 0
    sign_bit = 0
    if value < 0:
        sign_bit = 1 << 31
        value = -value
    exponent = _floor_log2(value)
    if exponent > 127:
        return sign_bit | 0x7F800000
    if exponent < -126:
        mantissa = _round_fraction_to_even_integer(value * (1 << 149))
        if mantissa == 0:
            return sign_bit
        if mantissa >= (1 << 23):
            return sign_bit | (1 << 23)
        return sign_bit | mantissa
    shift = 23 - exponent
    scaled = value * (1 << shift) if shift >= 0 else value / (1 << -shift)
    mantissa = _round_fraction_to_even_integer(scaled)
    if mantissa == (1 << 24):
        mantissa >>= 1
        exponent += 1
        if exponent > 127:
            return sign_bit | 0x7F800000
    return sign_bit | ((exponent + 127) << 23) | (mantissa - (1 << 23))


def bits_text(bits: int) -> str:
    return f"0x{bits:08x}"


def bits_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def exact_domain_proof(scale_bits: str = SCALE_BITS, zero_point: int = 0) -> dict[str, Any]:
    """Prove the frozen binary32 sequence for every legal uint8 input."""

    scale = bits_to_fraction(scale_bits)
    if scale <= 0:
        raise IdentityFusionError("scale must be positive")
    records: list[dict[str, Any]] = []
    mismatch_count = 0
    noninteger_exact_quotients = 0
    noninteger_binary32_quotients = 0
    maximum_pre_division_error = Fraction(0)
    maximum_exact_quotient_error = Fraction(0)
    maximum_binary32_quotient_error = Fraction(0)
    minimum_wrong_rounding_margin: Fraction | None = None
    worst_pre_division_u = 0
    worst_exact_quotient_u = 0
    worst_binary32_quotient_u = 0

    for u in range(256):
        centered = u - zero_point
        centered_bits = round_fraction_to_binary32_bits(Fraction(centered))
        centered_f32 = bits_to_fraction(bits_text(centered_bits))
        product_exact = centered_f32 * scale
        product_bits = round_fraction_to_binary32_bits(product_exact)
        product_f32 = bits_to_fraction(bits_text(product_bits))
        pre_division_error = abs(product_f32 - product_exact)
        quotient_exact = product_f32 / scale
        quotient_bits = round_fraction_to_binary32_bits(quotient_exact)
        quotient_f32 = bits_to_fraction(bits_text(quotient_bits))
        rounded_integer = _round_fraction_to_even_integer(quotient_f32)
        with_zero_point = rounded_integer + zero_point
        output = min(255, max(0, with_zero_point))
        if output != u:
            mismatch_count += 1
        if quotient_exact.denominator != 1:
            noninteger_exact_quotients += 1
        if quotient_f32.denominator != 1:
            noninteger_binary32_quotients += 1

        exact_quotient_error = abs(quotient_exact - centered)
        binary32_quotient_error = abs(quotient_f32 - centered)
        wrong_rounding_margin = Fraction(1, 2) - binary32_quotient_error
        if wrong_rounding_margin < 0:
            raise IdentityFusionError(
                f"quotient crossed a nearest-even boundary for u={u}"
            )
        if pre_division_error > maximum_pre_division_error:
            maximum_pre_division_error = pre_division_error
            worst_pre_division_u = u
        if exact_quotient_error > maximum_exact_quotient_error:
            maximum_exact_quotient_error = exact_quotient_error
            worst_exact_quotient_u = u
        if binary32_quotient_error > maximum_binary32_quotient_error:
            maximum_binary32_quotient_error = binary32_quotient_error
            worst_binary32_quotient_u = u
        if (
            minimum_wrong_rounding_margin is None
            or wrong_rounding_margin < minimum_wrong_rounding_margin
        ):
            minimum_wrong_rounding_margin = wrong_rounding_margin

        records.append(
            {
                "u": u,
                "centered_binary32_bits": bits_text(centered_bits),
                "dequant_product_binary32_bits": bits_text(product_bits),
                "dequant_product_binary32": bits_to_float(product_bits),
                "pre_division_error_exact": fraction_text(pre_division_error),
                "division_unrounded_exact": fraction_text(quotient_exact),
                "division_unrounded_is_integer": quotient_exact.denominator == 1,
                "division_binary32_bits": bits_text(quotient_bits),
                "division_binary32": bits_to_float(quotient_bits),
                "division_binary32_is_integer": quotient_f32.denominator == 1,
                "division_error_from_centered_exact": fraction_text(
                    binary32_quotient_error
                ),
                "nearest_even_integer": rounded_integer,
                "after_zero_point": with_zero_point,
                "clamped_uint8": output,
                "identity_pass": output == u,
            }
        )

    assert minimum_wrong_rounding_margin is not None
    domain_sha = canonical_json_sha256(records)
    return {
        "operation_order": [
            "binary32(uint8-zp)",
            "binary32_multiply_by_exact_scale",
            "metadata_only_view",
            "binary32_divide_by_same_exact_scale",
            "nearest_even_integer",
            "add_zero_point",
            "clamp_uint8",
        ],
        "scale_bits": scale_bits,
        "scale_exact_fraction": fraction_text(scale),
        "zero_point": zero_point,
        "input_domain": [0, 255],
        "domain_value_count": len(records),
        "mismatch_count": mismatch_count,
        "identity_for_all_values": mismatch_count == 0,
        "noninteger_unrounded_exact_quotient_count": noninteger_exact_quotients,
        "noninteger_binary32_quotient_count": noninteger_binary32_quotients,
        "maximum_pre_division_rounding_error": {
            "u": worst_pre_division_u,
            "exact_fraction": fraction_text(maximum_pre_division_error),
            "float": float(maximum_pre_division_error),
        },
        "maximum_unrounded_quotient_error": {
            "u": worst_exact_quotient_u,
            "exact_fraction": fraction_text(maximum_exact_quotient_error),
            "float": float(maximum_exact_quotient_error),
        },
        "maximum_binary32_quotient_error": {
            "u": worst_binary32_quotient_u,
            "exact_fraction": fraction_text(maximum_binary32_quotient_error),
            "float": float(maximum_binary32_quotient_error),
        },
        "minimum_margin_to_wrong_nearest_even_boundary": {
            "exact_fraction": fraction_text(minimum_wrong_rounding_margin),
            "float": float(minimum_wrong_rounding_margin),
        },
        "per_value_records_sha256": domain_sha,
        "per_value_records": records,
    }


def _request(bundle: dict[str, Any], hw_op_id: str) -> dict[str, Any]:
    for request in bundle["requests"]:
        if request["identity"]["hw_op_id"] == hw_op_id:
            return request
    raise IdentityFusionError(f"missing lowering request: {hw_op_id}")


def _node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in graph["nodes"]:
        if node["node_id"] == node_id:
            return node
    raise IdentityFusionError(f"missing graph node: {node_id}")


def _tensor(graph: dict[str, Any], tensor_id: str) -> dict[str, Any]:
    for tensor in graph["tensors"]:
        if tensor["tensor_id"] == tensor_id:
            return tensor
    raise IdentityFusionError(f"missing graph tensor: {tensor_id}")


def _parameter(request: dict[str, Any], name: str) -> dict[str, Any]:
    for parameter in request["typed_parameters"]:
        if parameter["name"] == name:
            return parameter
    raise IdentityFusionError(
        f"missing typed parameter {name}: {request['identity']['hw_op_id']}"
    )


def _port(request: dict[str, Any], role: str) -> dict[str, Any]:
    for port in request["ports"]["inputs"]:
        if port["role"] == role:
            return port
    raise IdentityFusionError(
        f"missing input port {role}: {request['identity']['hw_op_id']}"
    )


def extract_instance_descriptor(root: Path) -> dict[str, Any]:
    graph = load_json(root / "artifacts/w3/model_graph.json")
    bundle = load_json(root / "contracts/resnet50_r5_lowering_bundle.json")
    model_path = root / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    if (
        sha256_file(model_path) != MODEL_SHA256
        or graph["model_sha256"] != MODEL_SHA256
        or bundle["model_sha256"] != MODEL_SHA256
    ):
        raise IdentityFusionError("model identity changed")

    n71 = _node(graph, "node-0071")
    n72 = _node(graph, "node-0072")
    n73 = _node(graph, "node-0073")
    n74 = _node(graph, "node-0074")
    n75 = _node(graph, "node-0075")
    r72 = _request(bundle, "hwop-0072-00")
    r73 = _request(bundle, "hwop-0073-00")
    r74 = _request(bundle, "hwop-0074-00")
    r75 = _request(bundle, "hwop-0075-00")
    dscale = _parameter(r72, "x_scale")
    dzp = _parameter(r72, "x_zero_point")
    qscale = _parameter(r74, "y_scale")
    qzp = _parameter(r74, "y_zero_point")
    a_zp = _parameter(r75, "a_zero_point")
    node75_scale_tensor = _tensor(graph, n75["input_tensor_ids"][1])

    descriptor = {
        "model_sha256": graph["model_sha256"],
        "graph_nodes": [
            {
                "node_id": node["node_id"],
                "op_type": node["op_type"],
                "attributes": node["attributes"],
                "input_tensor_ids": node["input_tensor_ids"],
                "output_tensor_ids": node["output_tensor_ids"],
            }
            for node in (n71, n72, n73, n74, n75)
        ],
        "dequant": {
            "node_id": "node-0072",
            "hw_op_id": "hwop-0072-00",
            "input_tensor_id": SOURCE_TENSOR_ID,
            "input_dtype": r72["logical_geometry"]["input_dtypes"][0],
            "input_shape": r72["logical_geometry"]["input_shapes"][0],
            "output_tensor_id": OLD_DEQUANT_TENSOR_ID,
            "output_dtype": r72["logical_geometry"]["output_dtypes"][0],
            "output_shape": r72["logical_geometry"]["output_shapes"][0],
            "scale_bits": dscale["value"]["float32_bits"],
            "scale_dtype": dscale["value"]["dtype"],
            "scale_shape": dscale["value"]["shape"],
            "scale_value_sha256": dscale["value"]["value_sha256"],
            "zero_point": dzp["value"]["scalar"],
            "zero_point_dtype": dzp["value"]["dtype"],
            "zero_point_shape": dzp["value"]["shape"],
            "zero_point_value_sha256": dzp["value"]["value_sha256"],
            "axis": None,
            "quantization_granularity": "per_tensor",
            "operation_order": [
                "cast_uint8_to_binary32",
                "subtract_zero_point_exact",
                "binary32_multiply_scale",
            ],
        },
        "view": {
            "node_id": "node-0073",
            "hw_op_id": "hwop-0073-00",
            "axis": r73["logical_geometry"]["attributes"]["axis"],
            "input_tensor_id": OLD_DEQUANT_TENSOR_ID,
            "input_dtype": r73["logical_geometry"]["input_dtypes"][0],
            "input_shape": r73["logical_geometry"]["input_shapes"][0],
            "output_tensor_id": OLD_VIEW_TENSOR_ID,
            "output_dtype": r73["logical_geometry"]["output_dtypes"][0],
            "output_shape": r73["logical_geometry"]["output_shapes"][0],
            "original_element_order": "C_NCHW_trailing_unit_dims",
            "bypass_element_order": "C_NC",
            "bypass_transform": "metadata_only_drop_trailing_unit_dimensions",
        },
        "quant": {
            "node_id": "node-0074",
            "hw_op_id": "hwop-0074-00",
            "input_tensor_id": OLD_VIEW_TENSOR_ID,
            "input_dtype": r74["logical_geometry"]["input_dtypes"][0],
            "input_shape": r74["logical_geometry"]["input_shapes"][0],
            "output_tensor_id": TARGET_TENSOR_ID,
            "output_dtype": r74["logical_geometry"]["output_dtypes"][0],
            "output_shape": r74["logical_geometry"]["output_shapes"][0],
            "scale_bits": qscale["value"]["float32_bits"],
            "scale_dtype": qscale["value"]["dtype"],
            "scale_shape": qscale["value"]["shape"],
            "scale_value_sha256": qscale["value"]["value_sha256"],
            "zero_point": qzp["value"]["scalar"],
            "zero_point_dtype": qzp["value"]["dtype"],
            "zero_point_shape": qzp["value"]["shape"],
            "zero_point_value_sha256": qzp["value"]["value_sha256"],
            "axis": None,
            "quantization_granularity": "per_tensor",
            "operation_order": [
                "binary32_divide_scale",
                "nearest_even_integer",
                "add_zero_point",
                "clamp_uint8",
            ],
        },
        "downstream": {
            "node_id": "node-0075",
            "hw_op_id": "hwop-0075-00",
            "input_tensor_id": _port(r75, "a")["tensor_id"],
            "input_dtype": _port(r75, "a")["dtype"],
            "input_shape": _port(r75, "a")["shape"],
            "a_scale_tensor_id": n75["input_tensor_ids"][1],
            "a_scale_bits": qscale["value"]["float32_bits"],
            "a_scale_dtype": node75_scale_tensor["dtype"],
            "a_scale_shape": node75_scale_tensor["shape"],
            "a_scale_value_sha256": node75_scale_tensor["initializer_sha256"],
            "a_zero_point": a_zp["value"]["scalar"],
            "a_zero_point_dtype": a_zp["value"]["dtype"],
            "a_zero_point_shape": a_zp["value"]["shape"],
            "a_zero_point_value_sha256": a_zp["value"]["value_sha256"],
        },
        "rewrite": {
            "source_tensor_id": SOURCE_TENSOR_ID,
            "source_dtype": "uint8",
            "source_shape": [16, 2048, 1, 1],
            "alias_tensor_id": TARGET_TENSOR_ID,
            "alias_dtype": "uint8",
            "alias_shape": [16, 2048],
            "alias_byte_strides": [2048, 1],
            "axis": 1,
            "element_order": "C_NCHW_trailing_unit_dims_to_C_NC",
            "storage_offset_bytes": 0,
        },
    }
    validate_instance_descriptor(descriptor)
    return descriptor


def validate_instance_descriptor(descriptor: dict[str, Any]) -> None:
    d = descriptor["dequant"]
    v = descriptor["view"]
    q = descriptor["quant"]
    downstream = descriptor["downstream"]
    rewrite = descriptor["rewrite"]
    exact_equal_fields = (
        ("scale_bits", d["scale_bits"], q["scale_bits"]),
        ("scale_dtype", d["scale_dtype"], q["scale_dtype"]),
        ("scale_shape", d["scale_shape"], q["scale_shape"]),
        ("scale_value_sha256", d["scale_value_sha256"], q["scale_value_sha256"]),
        ("zero_point", d["zero_point"], q["zero_point"]),
        ("zero_point_dtype", d["zero_point_dtype"], q["zero_point_dtype"]),
        ("zero_point_shape", d["zero_point_shape"], q["zero_point_shape"]),
        (
            "zero_point_value_sha256",
            d["zero_point_value_sha256"],
            q["zero_point_value_sha256"],
        ),
        ("axis", d["axis"], q["axis"]),
        (
            "quantization_granularity",
            d["quantization_granularity"],
            q["quantization_granularity"],
        ),
    )
    for name, left, right in exact_equal_fields:
        if left != right:
            raise IdentityFusionError(f"qparam mismatch: {name}")
    if (
        d["scale_bits"] != SCALE_BITS
        or d["scale_dtype"] != "float32"
        or d["scale_shape"] != [1]
        or d["scale_value_sha256"] != SCALE_VALUE_SHA256
        or d["zero_point"] != 0
        or d["zero_point_dtype"] != "uint8"
        or d["zero_point_shape"] != [1]
        or d["zero_point_value_sha256"] != ZERO_POINT_VALUE_SHA256
        or d["axis"] is not None
        or d["quantization_granularity"] != "per_tensor"
    ):
        raise IdentityFusionError("frozen qparam identity changed")
    if (
        d["input_dtype"] != "uint8"
        or d["input_shape"] != [16, 2048, 1, 1]
        or d["output_dtype"] != "float32"
        or q["input_dtype"] != "float32"
        or q["input_shape"] != [16, 2048]
        or q["output_dtype"] != "uint8"
        or q["output_shape"] != [16, 2048]
    ):
        raise IdentityFusionError("frozen dtype or shape changed")
    if (
        v["axis"] != 1
        or v["input_dtype"] != "float32"
        or v["output_dtype"] != "float32"
        or v["input_shape"] != [16, 2048, 1, 1]
        or v["output_shape"] != [16, 2048]
        or v["bypass_transform"]
        != "metadata_only_drop_trailing_unit_dimensions"
        or rewrite["axis"] != 1
        or rewrite["source_dtype"] != "uint8"
        or rewrite["source_shape"] != [16, 2048, 1, 1]
        or rewrite["alias_dtype"] != "uint8"
        or rewrite["alias_shape"] != [16, 2048]
        or rewrite["alias_byte_strides"] != [2048, 1]
        or rewrite["element_order"] != "C_NCHW_trailing_unit_dims_to_C_NC"
        or rewrite["storage_offset_bytes"] != 0
    ):
        raise IdentityFusionError("View/order/layout/offset mismatch")
    if (
        downstream["input_tensor_id"] != TARGET_TENSOR_ID
        or downstream["input_dtype"] != "uint8"
        or downstream["input_shape"] != [16, 2048]
        or downstream["a_scale_bits"] != q["scale_bits"]
        or downstream["a_scale_dtype"] != q["scale_dtype"]
        or downstream["a_scale_shape"] != q["scale_shape"]
        or downstream["a_scale_value_sha256"] != q["scale_value_sha256"]
        or downstream["a_zero_point"] != q["zero_point"]
        or downstream["a_zero_point_dtype"] != q["zero_point_dtype"]
        or downstream["a_zero_point_shape"] != q["zero_point_shape"]
        or downstream["a_zero_point_value_sha256"]
        != q["zero_point_value_sha256"]
    ):
        raise IdentityFusionError("node0075 typed qdomain is not closed")


def negative_control_results(descriptor: dict[str, Any]) -> dict[str, Any]:
    mutations: dict[str, tuple[tuple[str, ...], Any]] = {
        "scale_bits": (("quant", "scale_bits"), "0x3cbf57ed"),
        "zero_point": (("quant", "zero_point"), 1),
        "dtype": (("rewrite", "alias_dtype"), "float32"),
        "axis": (("quant", "axis"), 0),
        "element_order": (("rewrite", "element_order"), "C_CN"),
        "layout": (("rewrite", "alias_byte_strides"), [1, 16]),
        "storage_offset": (("rewrite", "storage_offset_bytes"), 1),
    }
    results: dict[str, Any] = {}
    for name, (path, value) in mutations.items():
        candidate = copy.deepcopy(descriptor)
        cursor: dict[str, Any] = candidate
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        try:
            validate_instance_descriptor(candidate)
        except IdentityFusionError as error:
            results[name] = {
                "fail_closed": True,
                "error": str(error),
                "mutation_path": ".".join(path),
                "mutation_value": value,
            }
        else:
            results[name] = {
                "fail_closed": False,
                "error": None,
                "mutation_path": ".".join(path),
                "mutation_value": value,
            }
    if not all(item["fail_closed"] for item in results.values()):
        raise IdentityFusionError("one or more negative controls did not fail closed")
    return results


def _locked_source_receipts(contract: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    receipts = []
    for expected in contract["current_match_sources"]:
        path = root / expected["path"]
        if not path.is_file():
            raise IdentityFusionError(f"missing locked source: {expected['path']}")
        actual = file_identity(path, root)
        if (
            actual["sha256"] != expected["sha256"]
            or actual["bytes"] != expected["bytes"]
        ):
            raise IdentityFusionError(
                f"locked source changed: {expected['path']} "
                f"expected={expected['sha256']} actual={actual['sha256']}"
            )
        actual["gate"] = "current_match_fail_closed"
        receipts.append(actual)
    return receipts


def _validate_producer_endpoint(root: Path) -> dict[str, Any]:
    endpoint = load_json(
        root
        / "contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json"
    )
    producer = endpoint["owner_sections"]["QLinearGlobalAveragePool"]
    storage = producer["storage_identity"]
    coverage = producer["coverage"]
    base = producer["base_and_offset"]
    visibility = producer["visibility_and_lifetime"]
    if owner_section_sha256(producer) != producer["owner_section_content_sha256"]:
        raise IdentityFusionError("node0071 producer owner-section hash is stale")
    if (
        storage["storage_id"] != SOURCE_STORAGE_ID
        or storage["allocation_owner"] != "r5:hwop-0071-01:D"
        or storage["dtype"] != "uint8"
        or storage["logical_shape"] != [16, 2048, 1, 1]
        or storage["logical_byte_strides"] != [2048, 1, 1, 1]
        or storage["logical_valid_byte_span"] != 32768
        or storage["byte_offset_within_allocation"] != 0
        or base["active_producer_slice_count"] != 16
        or base["slice0_base_addr"] != "0x000a2000"
        or base["slice_address_stride_bytes"] != 33554432
        or coverage["bytes_per_active_slice"] != 2048
        or coverage["logical_valid_bytes"] != 32768
        or coverage["physical_written_bytes"] != 32768
        or coverage["physical_padding_bytes"] != 0
        or coverage["transaction_bytes"] != 32
        or coverage["transactions_per_active_slice"] != 64
        or coverage["local_ordered_address_sha256"] != ORDERED_ADDRESS_SHA256
        or coverage["local_written_byte_set_sha256"] != WRITTEN_BYTE_SET_SHA256
        or not coverage["logical_inverse_complete"]
        or not coverage["logical_inverse_unique"]
    ):
        raise IdentityFusionError("node0071 source storage/address/coverage changed")
    return {
        "storage_id": storage["storage_id"],
        "allocation_owner": storage["allocation_owner"],
        "dtype": storage["dtype"],
        "source_shape": storage["logical_shape"],
        "source_byte_strides": storage["logical_byte_strides"],
        "alias_shape": [16, 2048],
        "alias_byte_strides": [2048, 1],
        "alias_offset_bytes": 0,
        "active_slice_count": 16,
        "slice_base_formula": base["base_formula"],
        "slice0_base_addr": base["slice0_base_addr"],
        "slice_address_stride_bytes": base["slice_address_stride_bytes"],
        "bytes_per_active_slice": coverage["bytes_per_active_slice"],
        "total_valid_bytes": coverage["logical_valid_bytes"],
        "transaction_bytes": coverage["transaction_bytes"],
        "transactions_per_active_slice": coverage["transactions_per_active_slice"],
        "ordered_address_sha256": coverage["local_ordered_address_sha256"],
        "written_byte_set_sha256": coverage["local_written_byte_set_sha256"],
        "producer_visibility_event": visibility["producer_visibility_event"],
        "producer_local_visibility_evidence_accepted": visibility[
            "producer_local_visibility_evidence_accepted"
        ],
        "shared_multi_operator_barrier_materialized": visibility[
            "shared_multi_operator_barrier_materialized"
        ],
    }


def _validate_original_lifetime_blocker(root: Path) -> dict[str, Any]:
    lifetime = load_json(
        root / "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    )
    matches = [
        edge
        for edge in lifetime["typed_tensor_dag"]["edges"]
        if edge["producer_request_id"] == "r5:hwop-0074-00"
        and edge["consumer_request_id"] == "r5:hwop-0075-00"
        and edge["tensor_id"] == TARGET_TENSOR_ID
    ]
    if len(matches) != 1:
        raise IdentityFusionError("original node0074->node0075 edge identity changed")
    edge = matches[0]
    if (
        edge["dtype"] != "uint8"
        or edge["shape"] != [16, 2048]
        or edge["byte_count"] != 32768
        or edge["physical_allocation_status"]
        != "blocked_until_address_offset_and_lifetime_are_bound"
        or edge["logical_alias_eligible"] is not False
        or edge["implicit_register_or_buffer_reuse_allowed"] is not False
    ):
        raise IdentityFusionError("original node0074->node0075 lifetime gate changed")
    return {
        "edge_id": edge["edge_id"],
        "dtype": edge["dtype"],
        "shape": edge["shape"],
        "byte_count": edge["byte_count"],
        "original_logical_alias_eligible": edge["logical_alias_eligible"],
        "physical_allocation_status": edge["physical_allocation_status"],
        "implicit_reuse_allowed": edge[
            "implicit_register_or_buffer_reuse_allowed"
        ],
    }


def _validate_counterexample(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    binding = contract["accepted_rec_mul_counterexample"]
    source_path = root / binding["source"]["path"]
    if sha256_file(source_path) != binding["source"]["sha256"]:
        raise IdentityFusionError("accepted REC/MUL counterexample source changed")
    source = load_json(source_path)
    value = source["accepted_counterexample_binding"]
    for key in (
        "x_bits",
        "scale_bits",
        "divide_then_rne_uint8",
        "reciprocal_mul_then_rne_uint8",
    ):
        if binding[key] != value[key]:
            raise IdentityFusionError(f"REC/MUL counterexample changed at {key}")
    if (
        binding["retested"] is not False
        or binding["scope"]
        != "rejects generic REC/MUL as exact binary32 division; does not execute in paired-elimination bypass"
    ):
        raise IdentityFusionError("REC/MUL counterexample claim boundary widened")
    return binding


def _validate_canonical(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    path = root / contract["canonical_binding"]["path"]
    canonical = load_json(path)
    quant = canonical["owner_sections"]["QuantizeLinear"]
    contract_path = root / "contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json"
    expected_pointer = {
        "path": contract_path.relative_to(root).as_posix(),
        "sha256": sha256_file(contract_path),
    }
    if (
        quant["identity_fusion_contract"] != expected_pointer
        or quant["status"] != "APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER"
        or quant["reuse_class"] != "APPROVED_EQUIVALENT"
        or quant["reuse_status"]
        != "FROZEN_CHAIN_EQUIVALENT_GENERIC_DIVIDER_BLOCKER_RETAINED_OFF_PATH"
        or quant["numeric_capability"]["blocker_id"]
        != "B_QUANT_NODE0074_EXACT_DIVISION"
        or quant["numeric_capability"]["shared_blocker_id"]
        != "B_QUANT_TAIL_EXACT_FP32_DIVISION"
        or quant["numeric_capability"]["on_frozen_chain_execution_path"] is not False
        or any(quant["consumer_owned_endpoint_fields"].values())
        or quant["endpoint_claim"]["provisional_address_allowed"] is not False
        or quant["claim_boundary"]["integrated_endpoint_closed"] is not False
    ):
        raise IdentityFusionError("canonical QuantizeLinear fusion binding changed")
    if owner_section_sha256(quant) != quant["owner_section_content_sha256"]:
        raise IdentityFusionError("canonical QuantizeLinear owner-section hash is stale")
    for family in ("DequantizeLinear", "Flatten_View"):
        section = canonical["owner_sections"][family]
        expected_hash = contract["canonical_binding"]["foreign_owner_section_sha256"][
            family
        ]
        if (
            section["owner_section_content_sha256"] != expected_hash
            or owner_section_sha256(section) != expected_hash
        ):
            raise IdentityFusionError(f"foreign owner section changed: {family}")
    return {
        **file_identity(path, root),
        "quantize_owner_section_sha256": quant["owner_section_content_sha256"],
        "foreign_owner_sections_unchanged": True,
        "consumer_owned_endpoint_fields_all_null": True,
    }


def build_contract(root: Path) -> dict[str, Any]:
    descriptor = extract_instance_descriptor(root)
    proof = exact_domain_proof()
    if not proof["identity_for_all_values"]:
        raise IdentityFusionError("full uint8-domain identity proof failed")
    proof_summary = {
        key: value
        for key, value in proof.items()
        if key != "per_value_records"
    }
    semantic_paths = [
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/算子配置规则.md",
        ".agents/rules/NDP硬件字段语义.md",
        ".agents/rules/Flatten_View算子配置规则.md",
        ".agents/rules/DequantizeLinear算子配置规则.md",
        ".agents/rules/精确UINT8量化尾专项规则.md",
        "artifacts/reference_model/resnet50-v1-12-int8.onnx",
        "artifacts/w3/model_graph.json",
        "contracts/resnet50_r5_lowering_bundle.json",
        "contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json",
        "contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json",
        "contracts/operator_config/stage_state_lifetime_contract_v1.json",
    ]
    read_receipt_paths = [".agents/agent.md", ".agents/plan.md", *semantic_paths]
    canonical = load_json(
        root
        / "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json"
    )
    exact_audit_path = (
        root
        / "contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json"
    )
    exact_audit = load_json(exact_audit_path)
    return {
        "schema": SCHEMA,
        "test_id": TEST_ID,
        "status": "APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER",
        "reuse_class": "APPROVED_EQUIVALENT",
        "provenance": {
            "analysis_owner_thread": "019fa2c0-572b-7f21-ac5a-96e773dde534",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "model_sha256": MODEL_SHA256,
            "origin_skill": "academic-research-suite/experiment-agent",
            "mode": "validate",
            "verification_status": "VERIFIED_LOCAL_STATIC_AND_NUMERIC",
            "version_label": "v1",
        },
        "read_receipts": [
            {
                **file_identity(root / path, root),
                "gate": (
                    "mutable_provenance_only"
                    if path == ".agents/plan.md"
                    else "historical_read_receipt"
                ),
            }
            for path in read_receipt_paths
        ],
        "current_match_sources": [
            file_identity(root / path, root) for path in semantic_paths
        ],
        "rule_ids": [
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001",
        ],
        "instance_descriptor": descriptor,
        "qparam_identity": {
            "bitwise_identical": True,
            "scale_bits": SCALE_BITS,
            "scale_dtype": "float32",
            "scale_shape": [1],
            "scale_value_sha256": SCALE_VALUE_SHA256,
            "zero_point": 0,
            "zero_point_dtype": "uint8",
            "zero_point_shape": [1],
            "zero_point_value_sha256": ZERO_POINT_VALUE_SHA256,
            "axis": None,
            "quantization_granularity": "per_tensor",
            "downstream_node0075_a_qdomain_identical": True,
        },
        "exact_equivalence_expected": proof_summary,
        "accepted_rec_mul_counterexample": {
            "source": file_identity(exact_audit_path, root),
            "x_bits": exact_audit["accepted_counterexample_binding"]["x_bits"],
            "scale_bits": exact_audit["accepted_counterexample_binding"][
                "scale_bits"
            ],
            "divide_then_rne_uint8": exact_audit[
                "accepted_counterexample_binding"
            ]["divide_then_rne_uint8"],
            "reciprocal_mul_then_rne_uint8": exact_audit[
                "accepted_counterexample_binding"
            ]["reciprocal_mul_then_rne_uint8"],
            "retested": False,
            "scope": (
                "rejects generic REC/MUL as exact binary32 division; does not "
                "execute in paired-elimination bypass"
            ),
        },
        "graph_rewrite": {
            "adjudication": "APPROVED_EQUIVALENT",
            "scope": "frozen node0072->node0073->node0074 instance only",
            "remove_from_execution": [
                "r5:hwop-0072-00 arithmetic",
                "r5:hwop-0074-00 arithmetic",
            ],
            "replacement": (
                "metadata-only UINT8 alias from node0071 D/node0072 A source "
                "storage [16,2048,1,1] to node0075 A [16,2048]"
            ),
            "host_precompute_used": False,
            "scaled_rounded_saturated_or_final_tensor_replayed": False,
            "reciprocal_or_multiply_used_as_division": False,
            "old_fp32_endpoint_reused": False,
            "typed_rewrite_closed": True,
            "physical_integration_closed": False,
        },
        "endpoint_handoff": {
            "known_source_storage": _validate_producer_endpoint(root),
            "original_edge_gate": _validate_original_lifetime_blocker(root),
            "consumer_owned_endpoint_fields": {
                "final_storage_identity": None,
                "final_producer_base": None,
                "final_view_offset": None,
                "final_consumer_base": None,
                "final_read_coverage": None,
                "final_accepted_lifetime": None,
            },
            "provisional_address_allowed": False,
            "first_integration_blocker": {
                "id": "B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING",
                "kind": "WAIT_INTEGRATION_OWNER",
                "reason": (
                    "node0075 A final occurrence addresses/read acceptance, shared "
                    "allocator alias overlay, multi-operator visibility barrier, "
                    "and release lifetime are not materialized"
                ),
            },
            "next_owner": "QLinearMatMul/integration allocator+execplan owner",
            "required_patch_proposal": {
                "typed_edge": (
                    "node0071 D tensor-ab32f279540568c3 uint8[16,2048,1,1] "
                    "aliases node0075 A tensor-6fbd5707d5f08110 uint8[16,2048]"
                ),
                "allocation_owner": "r5:hwop-0071-01:D",
                "storage_id": SOURCE_STORAGE_ID,
                "active_slice_count": 16,
                "base_formula": (
                    "0x000a2000+(slice_id<<25), 0<=slice_id<16"
                ),
                "view_offset_bytes": 0,
                "required_read_bytes_per_slice": 2048,
                "required_total_read_bytes": 32768,
                "required_ordered_address_sha256": ORDERED_ADDRESS_SHA256,
                "required_written_byte_set_sha256": WRITTEN_BYTE_SET_SHA256,
                "first_legal_read": (
                    "after node0071 final uint8 D byte-set accepted and "
                    "node0071 completion/final barrier accepted"
                ),
                "release_event": (
                    "node0075 final A input-data accepted and no pending/replayed "
                    "read; fallback=node0075 completion accepted"
                ),
                "node0075_a_scale_bits": SCALE_BITS,
                "node0075_a_zero_point": 0,
                "required_owner_actions": [
                    "materialize graph rewrite/alias overlay",
                    "bind node0075 A occurrence addresses to the exact producer byte set",
                    "prove 32768-byte consumer read coverage and element-order inverse",
                    "bind allocator ownership without relocation or copy",
                    "bind producer visibility and consumer accepted-lifetime barriers",
                    "update canonical top-level cross-owner gates and claim boundary after integration proof",
                ],
                "canonical_top_level_handoff": {
                    "not_modified_by_quantize_owner": True,
                    "current_stale_reason_fields": {
                        "cross_owner_gates.quantize_exact_division": "OPEN",
                        "cross_owner_gates.same_storage_match": (
                            "BLOCKED_BY_NULL_QUANTIZE_ENDPOINT"
                        ),
                        "cross_owner_gates.producer_write_vs_consumer_read_coverage": (
                            "PRODUCER_READY_CONSUMER_PENDING_EXACT_DIVISION"
                        ),
                    },
                    "required_integration_owner_update": (
                        "replace exact-division-on-path wording with approved frozen "
                        "identity-fusion plus node0075 binding state; do not close "
                        "the generic divider blockers"
                    ),
                },
            },
        },
        "generic_capability_blockers": {
            "B_QUANT_NODE0074_EXACT_DIVISION": {
                "status": "OPEN_GENERIC_FAMILY_CAPABILITY",
                "on_this_frozen_chain_execution_path": False,
            },
            "B_QUANT_TAIL_EXACT_FP32_DIVISION": {
                "status": "OPEN_GENERIC_FAMILY_CAPABILITY",
                "on_this_frozen_chain_execution_path": False,
            },
        },
        "canonical_binding": {
            "path": (
                "contracts/operator_config/"
                "resnet50_node0072_node0074_shared_endpoint_v1.json"
            ),
            "foreign_owner_section_sha256": {
                family: canonical["owner_sections"][family][
                    "owner_section_content_sha256"
                ]
                for family in ("DequantizeLinear", "Flatten_View")
            },
            "quantize_owner_only_write_authorized": True,
        },
        "analysis_accounting": {
            "numeric_analysis_repeated": True,
            "reason": "new independent full-domain binary32 proof required by this task",
            "w3_or_golden_tensor_values_retested": False,
            "accepted_dequant_primitive_retested": False,
            "accepted_flatten_view_primitive_retested": False,
            "accepted_rec_mul_counterexample_retested": False,
            "consumed_reuse_assets": True,
            "reuse_assets": [
                "typed lowering and model graph",
                "node0071 producer endpoint address/coverage evidence",
                "original node0074->node0075 lifetime gate",
                "accepted REC/MUL counterexample",
            ],
        },
        "outputs": {
            "target_json": False,
            "mapping": False,
            "bitstream": False,
            "execplan": False,
            "sca": False,
            "server_package": False,
            "candidate_release": False,
        },
        "functional_rtl_modified": False,
        "server_files_inspected": False,
        "server_upload_or_run": False,
        "server_lease": False,
        "package_release": "NONE",
        "package_release_reason": "WAIT_INTEGRATION_OWNER",
        "claim_boundary": (
            "Local deterministic bit-exact semantic proof and Quantize-owned "
            "rewrite handoff only. Not a generic divider, target, integrated E2, "
            "E3, E4, E5, or server package."
        ),
        "rule_delta_proposal": {
            "required": False,
            "reason": (
                "Current APPROVED_EQUIVALENT, typed-edge, endpoint, lifetime, "
                "and fail-closed rules already cover the adjudication."
            ),
        },
    }


def validate_contract(contract_path: Path, root: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    if contract.get("schema") != SCHEMA or contract.get("test_id") != TEST_ID:
        raise IdentityFusionError("unexpected contract identity")
    if (
        contract["status"] != "APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER"
        or contract["reuse_class"] != "APPROVED_EQUIVALENT"
        or contract["package_release"] != "NONE"
        or contract["package_release_reason"] != "WAIT_INTEGRATION_OWNER"
        or any(contract["outputs"].values())
        or contract["functional_rtl_modified"] is not False
        or contract["server_files_inspected"] is not False
        or contract["server_upload_or_run"] is not False
    ):
        raise IdentityFusionError("claim or output boundary widened")
    if contract["provenance"][
        "analysis_owner_thread"
    ] != "019fa2c0-572b-7f21-ac5a-96e773dde534" or contract["provenance"][
        "return_target_thread"
    ] != "019fbec2-fe93-7e03-9314-cff6f222f33d":
        raise IdentityFusionError("thread provenance changed")
    locked = _locked_source_receipts(contract, root)
    descriptor = extract_instance_descriptor(root)
    if canonical_json_sha256(descriptor) != canonical_json_sha256(
        contract["instance_descriptor"]
    ):
        raise IdentityFusionError("materialized instance descriptor does not roundtrip")
    proof = exact_domain_proof()
    expected = {
        key: value for key, value in proof.items() if key != "per_value_records"
    }
    if canonical_json_sha256(expected) != canonical_json_sha256(
        contract["exact_equivalence_expected"]
    ):
        raise IdentityFusionError("materialized exact-equivalence summary changed")
    controls = negative_control_results(descriptor)
    producer = _validate_producer_endpoint(root)
    original_edge = _validate_original_lifetime_blocker(root)
    if canonical_json_sha256(producer) != canonical_json_sha256(
        contract["endpoint_handoff"]["known_source_storage"]
    ):
        raise IdentityFusionError("source endpoint handoff changed")
    if canonical_json_sha256(original_edge) != canonical_json_sha256(
        contract["endpoint_handoff"]["original_edge_gate"]
    ):
        raise IdentityFusionError("original lifetime blocker changed")
    endpoint = contract["endpoint_handoff"]
    if (
        any(endpoint["consumer_owned_endpoint_fields"].values())
        or endpoint["provisional_address_allowed"] is not False
        or endpoint["first_integration_blocker"]["kind"] != "WAIT_INTEGRATION_OWNER"
        or contract["graph_rewrite"]["typed_rewrite_closed"] is not True
        or contract["graph_rewrite"]["physical_integration_closed"] is not False
    ):
        raise IdentityFusionError("endpoint integration boundary widened")
    counterexample = _validate_counterexample(contract, root)
    canonical = _validate_canonical(contract, root)
    return {
        "schema": REPORT_SCHEMA,
        "test_id": TEST_ID,
        "status": contract["status"],
        "reuse_class": contract["reuse_class"],
        "contract": file_identity(contract_path, root),
        "current_match_sources": locked,
        "qparam_identity": contract["qparam_identity"],
        "exact_equivalence": proof,
        "negative_controls": controls,
        "accepted_rec_mul_counterexample": counterexample,
        "graph_rewrite": contract["graph_rewrite"],
        "endpoint_handoff": endpoint,
        "canonical_binding": canonical,
        "generic_capability_blockers": contract["generic_capability_blockers"],
        "analysis_accounting": contract["analysis_accounting"],
        "outputs": contract["outputs"],
        "package_release": contract["package_release"],
        "package_release_reason": contract["package_release_reason"],
        "claim_boundary": contract["claim_boundary"],
        "rule_delta_proposal": contract["rule_delta_proposal"],
        "passed": True,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_contract(root: Path, path: Path) -> dict[str, Any]:
    contract = build_contract(root)
    write_json(path, contract)
    return contract


def write_report(contract_path: Path, root: Path, report_path: Path) -> dict[str, Any]:
    report = validate_contract(contract_path, root)
    write_json(report_path, report)
    return report
