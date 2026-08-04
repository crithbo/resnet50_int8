from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import onnx
from onnx import numpy_helper

from .conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    ConvTargetRequest,
    build_conv_target_request,
)
from .conv_sa_contract import (
    SA_CHANNEL_LANES,
    SA_OUTPUT_LANES,
    SA_SPATIAL_LANES,
    validate_conv_3x3_sa_contract,
)
from .source_versions import (
    OFFICIAL_CONFIG_COMMIT,
    OFFICIAL_EXECPLAN_COMMIT,
    verify_ndp_source_checkout,
)


SCHEMA_VERSION = "resnet50-conv-typed-execplan-0.1"
USED_SLICES = "0b1111111111111111111111111111"
MODEL_RELATIVE = "artifacts/reference_model/resnet50-v1-12-int8.onnx"
E3_NODE_IDS = ("node-0004", "node-0008", "node-0003")
W4_SNAPSHOT_SHA256 = {
    "contracts/target_config_authority_audit.json": (
        "b81436245886aaca2c6e2ab26f52d6c70810daa18c835cb6f08ce683f4ffa8d3"
    ),
    "contracts/typed_config_parameter_contract.json": (
        "abbc87b0b13c92611a90fe1767b32b15fe9c49f23bee616ca2bb51219dd181bd"
    ),
}


class ConvExecplanTransportError(ValueError):
    """A typed Conv execplan lost identity, value bytes, or target binding."""


def _validate_accumulate_3x3_binding(
    binding: Mapping[str, Any], request: ConvTargetRequest
) -> dict[str, Any]:
    """Project-side extension for the explicit-halo 3x3 candidate ABI.

    The pinned NDPFuncModel validator intentionally remains the approved 1x1
    implementation.  This checker binds the new typed candidate without
    mutating that external source tree or claiming target execution support.
    """

    config_text = binding.get("config_text")
    contract_text = binding.get("semantic_contract_text")
    if not isinstance(config_text, str) or not isinstance(contract_text, str):
        raise ValueError("3x3 target binding requires exact config and contract text")
    if _sha256(config_text.encode("utf-8")) != binding.get("config_sha256"):
        raise ValueError("3x3 target config binding hash mismatch")
    if _sha256(contract_text.encode("utf-8")) != binding.get(
        "semantic_contract_sha256"
    ):
        raise ValueError("3x3 target semantic binding hash mismatch")
    config = json.loads(config_text)
    contract = json.loads(contract_text)
    spec = request.spec
    if (
        binding.get("transport_abi") != "conv_sa_q8k8_v2"
        or contract.get("transport_abi") != binding.get("transport_abi")
        or contract.get("config", {}).get("sha256") != binding["config_sha256"]
        or contract.get("instance", {}).get("node_id") != spec.node_id
        or contract.get("instance", {}).get("hw_op_ids")
        != [spec.accumulate_hw_op_id, spec.requant_hw_op_id]
        or tuple(contract.get("instance", {}).get("activation_shape", []))
        != spec.activation_shape
        or tuple(contract.get("instance", {}).get("weight_shape", []))
        != spec.weight_shape
        or tuple(contract.get("instance", {}).get("output_shape", []))
        != spec.output_shape
    ):
        raise ValueError("3x3 target semantic instance binding differs")
    halo_width = spec.activation_shape[3] + spec.pads[1] + spec.pads[3]
    halo_width_padded = (
        math.ceil(halo_width / SA_SPATIAL_LANES) * SA_SPATIAL_LANES
    )
    report = validate_conv_3x3_sa_contract(
        config,
        output_height=spec.output_height,
        output_width=spec.output_width,
        c_quartets=math.ceil(spec.c_tile / SA_CHANNEL_LANES),
        k_blocks=math.ceil(spec.k_tile / SA_OUTPUT_LANES),
        halo_width_padded=halo_width_padded,
    )
    return {
        "status": "validated",
        "validation_scope": "project_static_explicit_halo_3x3_candidate",
        "config_sha256": binding["config_sha256"],
        "semantic_contract_sha256": binding["semantic_contract_sha256"],
        "transport_abi": binding["transport_abi"],
        "loop_count": len(config["dram_loop_configs"]),
        "lc_pe_count": len(config["lc_pe_configs"]),
        "stream_targets": [
            config["stream_engine"][name]["target"]
            for name in sorted(config["stream_engine"])
        ],
        "n2n_mem_loop": report["high_ring_steps"],
        "n2n_src_slice_sel": 1,
        "n2n_dst_slice_sel": 1,
        "n2n_ping_pong": 0,
        "port_role_map": contract.get("port_semantics"),
    }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    return _sha256(np.ascontiguousarray(value).tobytes(order="C"))


def _float32_bits(values: np.ndarray) -> list[str]:
    array = np.ascontiguousarray(values, dtype=np.float32).reshape(-1)
    return [f"0x{int(item):08x}" for item in array.view(np.uint32)]


def _load_initializers(project_root: Path) -> dict[str, np.ndarray]:
    model = onnx.load(str(project_root / MODEL_RELATIVE), load_external_data=True)
    return {
        item.name: np.ascontiguousarray(numpy_helper.to_array(item))
        for item in model.graph.initializer
    }


def _parameter_values(request: ConvTargetRequest) -> dict[str, np.ndarray]:
    initializers = _load_initializers(request.project_root)
    values: dict[str, np.ndarray] = {}
    for name in (
        "bias",
        "w_scale",
        "w_zero_point",
        "x_scale",
        "x_zero_point",
        "y_scale",
        "y_zero_point",
    ):
        binding = request.spec.tensor(name)
        if binding.onnx_name is None or binding.onnx_name not in initializers:
            raise ConvExecplanTransportError(f"initializer payload is missing for {name}")
        value = initializers[binding.onnx_name]
        if tuple(value.shape) != binding.shape or str(value.dtype) != binding.dtype:
            raise ConvExecplanTransportError(f"initializer dtype/shape differs for {name}")
        if _array_sha256(value) != request.spec.parameter_hash(name):
            raise ConvExecplanTransportError(f"initializer value hash differs for {name}")
        values[name] = value
    values["requant_multiplier"] = np.asarray(
        np.float32(values["x_scale"].reshape(-1)[0])
        * values["w_scale"].astype(np.float32)
        / np.float32(values["y_scale"].reshape(-1)[0]),
        dtype=np.float32,
    )
    if _array_sha256(values["requant_multiplier"]) != request.spec.requant_multiplier_sha256:
        raise ConvExecplanTransportError("derived requant multiplier hash differs")
    return values


def _artifact(
    project_root: Path,
    *,
    artifact_id: str,
    role: str,
    relative_path: str,
) -> dict[str, Any]:
    path = project_root / relative_path
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConvExecplanTransportError(f"target artifact is not UTF-8 JSON: {path}") from error
    if not isinstance(parsed, dict):
        raise ConvExecplanTransportError(f"target artifact JSON root is not an object: {path}")
    return {
        "artifact_id": artifact_id,
        "role": role,
        "path": relative_path.replace("\\", "/"),
        "sha256": _sha256(payload),
        "raw_text": text,
    }


def _tensor(
    request: ConvTargetRequest,
    port: str,
    execution_shape: tuple[int, int, int],
    *,
    source: dict[str, str] | None = None,
) -> dict[str, Any]:
    binding = request.spec.tensor(port)
    value: dict[str, Any] = {
        "shape": list(execution_shape),
        "logical_shape": list(binding.shape),
        "dtype": binding.dtype,
        "tensor_id": binding.tensor_id,
        "identity_sha256": binding.identity_sha256,
        "remapping": None,
    }
    if source is not None:
        value["source"] = source
    return value


def _target_binding(
    location: str,
    encoding: str,
    derivation: str,
    indices: range | list[int] | tuple[int, ...],
    artifact_id: str | None = None,
) -> dict[str, Any]:
    return {
        "location": location,
        "encoding": encoding,
        "derivation": derivation,
        "element_indices": list(indices),
        "artifact_id": artifact_id,
    }


def _constant(
    request: ConvTargetRequest,
    name: str,
    value: np.ndarray,
    target_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    if name == "requant_multiplier":
        tensor_id = f"{request.spec.requant_hw_op_id}.derived.requant_multiplier"
        identity_sha256 = request.spec.requant_multiplier_sha256
        source_kind = "derived"
        source_parameter_ids = [
            request.spec.tensor(port).tensor_id for port in ("x_scale", "w_scale", "y_scale")
        ]
    else:
        binding = request.spec.tensor(name)
        tensor_id = binding.tensor_id
        identity_sha256 = binding.identity_sha256
        source_kind = "initializer"
        source_parameter_ids = []
    result: dict[str, Any] = {
        "tensor_id": tensor_id,
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "identity_sha256": identity_sha256,
        "value_sha256": _array_sha256(array),
        "values": array.reshape(-1).tolist(),
        "axis": 0 if array.size > 1 else None,
        "source_kind": source_kind,
        "source_parameter_ids": source_parameter_ids,
        "target_bindings": target_bindings,
    }
    if array.dtype == np.dtype("float32"):
        result["float32_bits"] = _float32_bits(array)
    else:
        result["float32_bits"] = None
    return result


def build_conv_execplan_request(project_root: Path, node_id: str) -> dict[str, Any]:
    root = project_root.resolve()
    request = build_conv_target_request(root, node_id)
    spec = request.spec
    values = _parameter_values(request)
    instance_id = f"conv:{spec.node_id}:{spec.accumulate_hw_op_id}+{spec.requant_hw_op_id}"
    spatial = spec.output_height * spec.output_width

    accumulate_config_id = f"{spec.accumulate_hw_op_id}.config"
    semantic_contract_id = f"{spec.accumulate_hw_op_id}.semantics"
    requant_manifest_id = f"{spec.requant_hw_op_id}.manifest"
    requant_encoder_contract_id = f"{spec.requant_hw_op_id}.encoder-contract"
    shard_artifact_ids = [
        f"{spec.requant_hw_op_id}.shard-{index:02d}"
        for index in range(spec.requant_shard_count)
    ]
    accumulate_artifacts = [
        _artifact(
            root,
            artifact_id=accumulate_config_id,
            role="accumulate_config",
            relative_path=request.accumulate_config_relative,
        ),
        _artifact(
            root,
            artifact_id=semantic_contract_id,
            role="semantic_contract",
            relative_path=request.semantic_contract_relative,
        ),
    ]
    requant_artifacts = [
        _artifact(
            root,
            artifact_id=requant_manifest_id,
            role="requant_manifest",
            relative_path=f"{request.requant_root_relative}/manifest.json",
        )
    ]
    has_requant_encoder_contract = request.requant_encoder_contract_path.is_file()
    if has_requant_encoder_contract:
        requant_artifacts.append(
            _artifact(
                root,
                artifact_id=requant_encoder_contract_id,
                role="requant_encoder_contract",
                relative_path=(
                    f"{request.requant_root_relative}/encoder_contract.json"
                ),
            )
        )
    requant_artifacts.extend(
        _artifact(
            root,
            artifact_id=artifact_id,
            role="requant_shard",
            relative_path=(
                f"{request.requant_root_relative}/shard-{index:02d}.json"
            ),
        )
        for index, artifact_id in enumerate(shard_artifact_ids)
    )
    requant_manifest = json.loads(requant_artifacts[0]["raw_text"])

    accumulate_constants = {
        "x_zero_point": _constant(
            request,
            "x_zero_point",
            values["x_zero_point"],
            [
                _target_binding(
                    "physical_bundle:x_zero_point",
                    "uint8_little_endian",
                    "center A before INT32 accumulation",
                    [0],
                )
            ],
        ),
        "w_zero_point": _constant(
            request,
            "w_zero_point",
            values["w_zero_point"],
            [
                _target_binding(
                    "physical_bundle:w_zero_point",
                    "int8_little_endian",
                    "center B per output channel before INT32 accumulation",
                    range(spec.output_channels),
                )
            ],
        ),
        "bias": _constant(
            request,
            "bias",
            values["bias"],
            [
                _target_binding(
                    "physical_bundle:bias",
                    "int32_little_endian",
                    "initialize first-K INT32 psum with ONNX bias",
                    range(spec.output_channels),
                )
            ],
        ),
    }

    derivation_binding = lambda name, count: _target_binding(
        f"derivation:{spec.requant_hw_op_id}.requant_multiplier/{name}",
        "fp32_source",
        "float32(x_scale * w_scale / y_scale)",
        range(count),
    )
    requant_constants = {
        "x_scale": _constant(
            request,
            "x_scale",
            values["x_scale"],
            [derivation_binding("x_scale", 1)],
        ),
        "w_scale": _constant(
            request,
            "w_scale",
            values["w_scale"],
            [derivation_binding("w_scale", spec.output_channels)],
        ),
        "y_scale": _constant(
            request,
            "y_scale",
            values["y_scale"],
            [derivation_binding("y_scale", 1)],
        ),
    }
    y_zero_bindings = [
        _target_binding(
            f"config_json:{requant_manifest_id}#/requant/output_zero_point",
            "uint8_json_integer",
            "identity",
            [0],
            requant_manifest_id,
        )
    ]
    multiplier_bindings: list[dict[str, Any]] = []
    for shard, artifact_id in zip(
        requant_manifest["shards"], shard_artifact_ids, strict=True
    ):
        channels = shard["channels"]
        y_zero_bindings.append(
            _target_binding(
                f"config_json:{artifact_id}#/general_array/PE_array/*/inport2/constant",
                "fp32_magic_add_output_zero_point",
                "float32(12582912 + y_zero_point)",
                [0],
                artifact_id,
            )
        )
        multiplier_bindings.append(
            _target_binding(
                f"config_json:{artifact_id}#/general_array/PE_array/[PE00,PE02,PE10,PE12,PE20,PE22,PE30,PE32]/inport1/constant",
                "fp32_json_number",
                "float32(x_scale * w_scale[channel] / y_scale)",
                channels,
                artifact_id,
            )
        )
    requant_constants["y_zero_point"] = _constant(
        request, "y_zero_point", values["y_zero_point"], y_zero_bindings
    )
    requant_constants["requant_multiplier"] = _constant(
        request,
        "requant_multiplier",
        values["requant_multiplier"],
        multiplier_bindings,
    )

    external = {"type": "external"}
    accumulate_op_id = f"{spec.accumulate_hw_op_id}.exec"
    requant_op_id = f"{spec.requant_hw_op_id}.exec"
    request_value = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": f"{instance_id}:typed-transport",
        "used_slices": USED_SLICES,
        "operators": [
            {
                "id": accumulate_op_id,
                "type": "resnet_qlinearconv_int32_accumulate",
                "instance_id": instance_id,
                "stage": "accumulate",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": _tensor(request, "A", (spec.batch_size, spatial, spec.input_channels), source=external),
                    "B": _tensor(request, "B", (1, spec.input_channels, spec.output_channels), source=external),
                    "C": _tensor(request, "bias", (1, 1, spec.output_channels), source=external),
                },
                "output": _tensor(request, "P", (spec.batch_size, spatial, spec.output_channels)),
                "attributes": {
                    "node_id": spec.node_id,
                    "hw_op_id": spec.accumulate_hw_op_id,
                    "stage_index": 0,
                    "geometry": {
                        "activation_shape": list(spec.activation_shape),
                        "weight_shape": list(spec.weight_shape),
                        "output_shape": list(spec.output_shape),
                        "kernel": list(spec.kernel),
                        "strides": list(spec.strides),
                        "pads": list(spec.pads),
                        "dilations": list(spec.dilations),
                        "group": spec.group,
                    },
                    "target": {
                        "transport_abi": request.transport_abi,
                        "slice_count": 28,
                        "communication_domain": spec.communication_domain,
                        "n2n": {
                            "mem_loop": spec.n2n_mem_loop,
                            "src_slice_sel": spec.n2n_src_slice_sel,
                            "dst_slice_sel": spec.n2n_dst_slice_sel,
                            "ping_pong": spec.n2n_ping_pong,
                        },
                    },
                    "artifact_relationship": {
                        "config_artifact_id": accumulate_config_id,
                        "semantic_contract_artifact_id": semantic_contract_id,
                    },
                },
                "constants": accumulate_constants,
                "config_artifacts": accumulate_artifacts,
            },
            {
                "id": requant_op_id,
                "type": "resnet_qlinearconv_uint8_requant",
                "instance_id": instance_id,
                "stage": "requantize",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": _tensor(
                        request,
                        "P",
                        (spec.batch_size, spatial, spec.output_channels),
                        source={"type": "operator", "operator_id": accumulate_op_id},
                    )
                },
                "output": _tensor(request, "D", (spec.batch_size, spatial, spec.output_channels)),
                "attributes": {
                    "node_id": spec.node_id,
                    "hw_op_id": spec.requant_hw_op_id,
                    "stage_index": 1,
                    "target": {
                        "transport_abi": request.transport_abi,
                        "slice_count": 28,
                        "communication_domain": spec.communication_domain,
                        "ga_lane_count": spec.ga_lane_count,
                        "required_loop_ends": [9408, 2352],
                        "alignment_bytes": spec.alignment_bytes,
                        "flush_count_per_logical_output": 1,
                    },
                    "artifact_relationship": {
                        "cardinality": "one_manifest_to_many_shards",
                        "manifest_artifact_id": requant_manifest_id,
                        "member_artifact_ids": shard_artifact_ids,
                        "encoder_contract_artifact_id": (
                            requant_encoder_contract_id
                            if has_requant_encoder_contract
                            else None
                        ),
                    },
                    "coverage": {
                        "channel_count": spec.output_channels,
                        "shard_count": spec.requant_shard_count,
                    },
                },
                "constants": requant_constants,
                "config_artifacts": requant_artifacts,
            },
        ],
    }
    validate_conv_execplan_request(request_value, root, expected_node_id=node_id)
    return request_value


def _load_official_parser(project_root: Path):
    source = project_root / "ndp-sim-ref" / "model_execplan" / "src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from execution_plan_generator.json_loader import (  # type: ignore[import-not-found]
        execution_plan_to_dict,
        parse_execution_plan_dict,
    )

    return parse_execution_plan_dict, execution_plan_to_dict


def _load_ndp_validators(project_root: Path):
    module_path = project_root / "NDPFuncModel" / "tools" / "physical_image_probe.py"
    ndp_root = project_root / "NDPFuncModel"
    if str(ndp_root) not in sys.path:
        sys.path.insert(0, str(ndp_root))
    module_name = "_resnet50_ndp_physical_image_probe"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ConvExecplanTransportError("cannot load NDP target validators")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return (
        module._validate_accumulate_target_config_binding,
        module._validate_requant_config_binding,
    )


def _artifact_map(operator: Any) -> dict[str, Any]:
    return {item.role: item for item in operator.config_artifacts}


def _validate_tensor_metadata(operator: Any, request: ConvTargetRequest) -> None:
    ports = (
        [(operator.inputs["A"], "A"), (operator.inputs["B"], "B"), (operator.inputs["C"], "bias"), (operator.output, "P")]
        if operator.stage == "accumulate"
        else [(operator.inputs["A"], "P"), (operator.output, "D")]
    )
    for tensor, port in ports:
        binding = request.spec.tensor(port)
        if (
            tensor.tensor_id != binding.tensor_id
            or tensor.dtype != binding.dtype
            or tensor.logical_shape != binding.shape
            or tensor.identity_sha256 != binding.identity_sha256
        ):
            raise ConvExecplanTransportError(f"typed tensor metadata differs for {port}")


def _validate_constants(operator: Any, request: ConvTargetRequest) -> None:
    required = (
        {"x_zero_point", "w_zero_point", "bias"}
        if operator.stage == "accumulate"
        else {"x_scale", "w_scale", "y_scale", "y_zero_point", "requant_multiplier"}
    )
    if set(operator.constants) != required:
        raise ConvExecplanTransportError(
            f"{operator.stage} typed constant coverage differs: {sorted(operator.constants)}"
        )
    for name, constant in operator.constants.items():
        expected_sha = (
            request.spec.requant_multiplier_sha256
            if name == "requant_multiplier"
            else request.spec.parameter_hash(name)
        )
        if constant.value_sha256 != expected_sha:
            raise ConvExecplanTransportError(f"typed constant hash differs for {name}")
        if math.prod(constant.shape) > 1 and constant.axis != 0:
            raise ConvExecplanTransportError(f"per-channel axis was lost for {name}")
        if not constant.target_bindings:
            raise ConvExecplanTransportError(f"target write/derivation binding is missing for {name}")


def _validate_artifact_bytes(operator: Any, project_root: Path) -> None:
    root = project_root.resolve()
    for artifact in operator.config_artifacts:
        relative = Path(artifact.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ConvExecplanTransportError(f"target artifact path escapes project root: {artifact.path}")
        path = (root / relative).resolve()
        if root not in path.parents:
            raise ConvExecplanTransportError(f"target artifact path escapes project root: {artifact.path}")
        payload = path.read_bytes()
        if (
            _sha256(payload) != artifact.sha256
            or payload != artifact.raw_text.encode("utf-8")
        ):
            raise ConvExecplanTransportError(f"target artifact content/SHA differs: {artifact.path}")


def validate_conv_execplan_request(
    value: Mapping[str, Any],
    project_root: Path,
    *,
    expected_node_id: str | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    if value.get("schema_version") != SCHEMA_VERSION or "params" in value:
        raise ConvExecplanTransportError(
            "Conv typed execplan schema differs or reuses legacy integer params"
        )
    parse_plan, plan_to_dict = _load_official_parser(root)
    try:
        plan = parse_plan(dict(value))
        round_trip = parse_plan(plan_to_dict(plan))
    except Exception as error:
        raise ConvExecplanTransportError(f"official execplan typed parse failed: {error}") from error
    if plan != round_trip or len(plan.operators) != 2:
        raise ConvExecplanTransportError("official execplan typed round-trip differs")
    accumulate, requant = plan.operators
    node_id = accumulate.attributes.get("node_id")
    request = build_conv_target_request(root, str(node_id))
    spec = request.spec
    expected_instance = f"conv:{spec.node_id}:{spec.accumulate_hw_op_id}+{spec.requant_hw_op_id}"
    if (
        expected_node_id is not None
        and node_id != expected_node_id
        or accumulate.instance_id != expected_instance
        or requant.instance_id != expected_instance
        or accumulate.stage != "accumulate"
        or requant.stage != "requantize"
        or requant.attributes.get("node_id") != node_id
        or accumulate.used_slice_count() != 28
        or requant.used_slice_count() != 28
        or accumulate.attributes.get("target", {}).get("slice_count") != 28
        or requant.attributes.get("target", {}).get("slice_count") != 28
    ):
        raise ConvExecplanTransportError("Conv instance/stage/28-slice identity differs")
    if (
        accumulate.attributes.get("hw_op_id") != spec.accumulate_hw_op_id
        or requant.attributes.get("hw_op_id") != spec.requant_hw_op_id
    ):
        raise ConvExecplanTransportError("Conv hw_op identity differs")
    accumulate_target = accumulate.attributes.get("target", {})
    requant_target = requant.attributes.get("target", {})
    if (
        accumulate_target.get("transport_abi") != request.transport_abi
        or requant_target.get("transport_abi") != request.transport_abi
    ):
        raise ConvExecplanTransportError(
            "Conv transport ABI is missing, unknown, or differs between stages"
        )
    _validate_tensor_metadata(accumulate, request)
    _validate_tensor_metadata(requant, request)
    _validate_constants(accumulate, request)
    _validate_constants(requant, request)
    _validate_artifact_bytes(accumulate, root)
    _validate_artifact_bytes(requant, root)

    accumulate_roles = _artifact_map(accumulate)
    requant_roles = _artifact_map(requant)
    if set(accumulate_roles) != {"accumulate_config", "semantic_contract"}:
        raise ConvExecplanTransportError("accumulate artifact roles differ")
    expected_requant_roles = {"requant_manifest", "requant_shard"}
    has_requant_encoder_contract = request.requant_encoder_contract_path.is_file()
    if has_requant_encoder_contract:
        expected_requant_roles.add("requant_encoder_contract")
    if set(requant_roles) != expected_requant_roles:
        raise ConvExecplanTransportError("requant artifact roles differ")
    shard_artifacts = [item for item in requant.config_artifacts if item.role == "requant_shard"]
    relationship = requant.attributes.get("artifact_relationship", {})
    if (
        relationship.get("cardinality") != "one_manifest_to_many_shards"
        or relationship.get("manifest_artifact_id") != requant_roles["requant_manifest"].artifact_id
        or relationship.get("member_artifact_ids") != [item.artifact_id for item in shard_artifacts]
        or len(shard_artifacts) != spec.requant_shard_count
        or (
            has_requant_encoder_contract
            and relationship.get("encoder_contract_artifact_id")
            != requant_roles["requant_encoder_contract"].artifact_id
        )
    ):
        raise ConvExecplanTransportError("requant manifest one-to-many relationship differs")

    validate_accumulate, validate_requant = _load_ndp_validators(root)
    try:
        accumulate_binding = {
            "transport_abi": request.transport_abi,
            "config_text": accumulate_roles["accumulate_config"].raw_text,
            "config_sha256": accumulate_roles["accumulate_config"].sha256,
            "semantic_contract_text": accumulate_roles["semantic_contract"].raw_text,
            "semantic_contract_sha256": accumulate_roles["semantic_contract"].sha256,
        }
        accumulate_result = (
            _validate_accumulate_3x3_binding(accumulate_binding, request)
            if spec.kernel == (3, 3)
            else validate_accumulate(accumulate_binding)
        )
        requant_result = validate_requant(
            {
                "manifest_text": requant_roles["requant_manifest"].raw_text,
                "manifest_sha256": requant_roles["requant_manifest"].sha256,
                "configs": [
                    {
                        "config_path": item.path,
                        "config_text": item.raw_text,
                        "config_sha256": item.sha256,
                    }
                    for item in shard_artifacts
                ],
            }
        )
    except Exception as error:
        raise ConvExecplanTransportError(f"NDP target config validation failed: {error}") from error
    if (
        requant_result.get("channel_count") != spec.output_channels
        or requant_result.get("shard_count") != spec.requant_shard_count
        or requant_result.get("unique_flush_count") != spec.output_channels
        or requant_result.get("flush_count_per_logical_output") != 1
    ):
        raise ConvExecplanTransportError("NDP requant coverage/flush result differs")
    return {
        "status": "typed_transport_validated",
        "node_id": spec.node_id,
        "instance_id": expected_instance,
        "operator_count": 2,
        "transport_abi": request.transport_abi,
        "config_artifact_count": len(accumulate.config_artifacts) + len(requant.config_artifacts),
        "typed_constant_count": len(accumulate.constants) + len(requant.constants),
        "requant_channel_count": requant_result["channel_count"],
        "requant_shard_count": requant_result["shard_count"],
        "unique_flush_count": requant_result["unique_flush_count"],
        "n2n": {
            "mem_loop": accumulate_result["n2n_mem_loop"],
            "src_slice_sel": accumulate_result["n2n_src_slice_sel"],
            "dst_slice_sel": accumulate_result["n2n_dst_slice_sel"],
            "ping_pong": accumulate_result["n2n_ping_pong"],
        },
    }


def canonical_execplan_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def build_conv_execplan_transport_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    verify_ndp_source_checkout(root / "ndp-sim-ref", require_clean=False)
    lock = json.loads((root / "repos.lock.json").read_text(encoding="utf-8"))
    locked = {item["name"]: item["commit"] for item in lock["repositories"]}
    if locked.get("ndp-sim-ref") != OFFICIAL_EXECPLAN_COMMIT:
        raise ConvExecplanTransportError("repository lock lost the execplan transport commit")
    transport_audit_path = root / "contracts" / "target_execplan_transport_audit.json"
    transport_audit = json.loads(transport_audit_path.read_text(encoding="utf-8"))
    if (
        transport_audit.get("source", {}).get("execplan_commit")
        != OFFICIAL_EXECPLAN_COMMIT
        or transport_audit.get("ga_quant_add_probe", {})
        .get("execplan_qparam_binding", {})
        .get("status")
        != "typed_transport_available"
    ):
        raise ConvExecplanTransportError("W5 target execplan transport audit differs")
    instances = []
    for node_id in E3_NODE_IDS:
        request = build_conv_target_request(root, node_id)
        path = request.preflight_path.parent / "execplan_request.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        validation = validate_conv_execplan_request(
            value, root, expected_node_id=node_id
        )
        instances.append(
            {
                "node_id": node_id,
                "hw_op_ids": [
                    request.spec.accumulate_hw_op_id,
                    request.spec.requant_hw_op_id,
                ],
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path.read_bytes()),
                "size_bytes": path.stat().st_size,
                "validation": validation,
            }
        )
    snapshots = []
    for relative, expected_sha256 in W4_SNAPSHOT_SHA256.items():
        path = root / relative
        observed = _sha256(path.read_bytes())
        if observed != expected_sha256:
            raise ConvExecplanTransportError(f"approved W4 snapshot drifted: {relative}")
        snapshots.append({"path": relative, "sha256": observed, "unchanged": True})
    return {
        "schema_version": "0.1",
        "contract_type": "conv_execplan_typed_transport_closure",
        "status": "resolved_for_closed_conv_instances",
        "former_blocker": "B_EXECPLAN_TYPED_TRANSPORT",
        "source": {
            "config_baseline_commit": OFFICIAL_CONFIG_COMMIT,
            "execplan_commit": OFFICIAL_EXECPLAN_COMMIT,
            # This is historical W5 evidence.  Keep its proven source identity
            # independent from the bootstrap lock, which may intentionally
            # select an earlier public/distributable NDPFuncModel revision.
            "ndpfuncmodel_commit": "a1d975ee2d6d9200b8df0deea3e2ffc13ce0d05e",
            "transport_audit": {
                "path": transport_audit_path.relative_to(root).as_posix(),
                "sha256": _sha256(transport_audit_path.read_bytes()),
                "size_bytes": transport_audit_path.stat().st_size,
            },
        },
        "schema_guarantees": {
            "operator_spec_fields": [
                "instance_id",
                "stage",
                "attributes",
                "constants",
                "config_artifacts",
            ],
            "legacy_integer_params_reused_for_fp32": False,
            "tensor_metadata": [
                "tensor_id",
                "dtype",
                "logical_shape",
                "identity_sha256",
                "value_sha256",
                "axis",
            ],
            "config_binding": "exact UTF-8 JSON raw_text plus SHA-256",
            "substage_identity": "accumulate and requantize share one instance_id",
            "requant_cardinality": "one manifest to many shards",
        },
        "negative_tests": [
            "missing_scale",
            "missing_zero_point",
            "missing_bias",
            "per_channel_axis_loss",
            "float_to_integer_truncation",
            "legacy_16_slice_mask",
            "config_raw_text_or_sha_drift",
        ],
        "instances": instances,
        "approved_w4_snapshots": snapshots,
        "boundary": {
            "g5_passed": False,
            "g6_passed": False,
            "g8_passed": False,
            "hardware_execution_proven": False,
            "whole_network_execplan_generated": False,
            "operator_specific_bindings_outside_closed_conv_instances": "pending",
            "conv_shape_family_parallel_expansion_allowed": True,
        },
    }


def validate_conv_execplan_transport_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if (
        value.get("schema_version") != "0.1"
        or value.get("contract_type") != "conv_execplan_typed_transport_closure"
        or value.get("status") != "resolved_for_closed_conv_instances"
        or value.get("former_blocker") != "B_EXECPLAN_TYPED_TRANSPORT"
        or value.get("source", {}).get("config_baseline_commit")
        != OFFICIAL_CONFIG_COMMIT
        or value.get("source", {}).get("execplan_commit")
        != OFFICIAL_EXECPLAN_COMMIT
        or value.get("source", {}).get("ndpfuncmodel_commit")
        != "a1d975ee2d6d9200b8df0deea3e2ffc13ce0d05e"
    ):
        raise ConvExecplanTransportError("typed transport closure identity differs")
    instances = value.get("instances", [])
    if [item.get("node_id") for item in instances] != list(E3_NODE_IDS):
        raise ConvExecplanTransportError("typed transport instance coverage differs")
    for item in instances:
        path = project_root.resolve() / str(item.get("path", ""))
        if (
            not path.is_file()
            or _sha256(path.read_bytes()) != item.get("sha256")
            or path.stat().st_size != item.get("size_bytes")
            or item.get("validation", {}).get("status")
            != "typed_transport_validated"
        ):
            raise ConvExecplanTransportError("typed transport request evidence differs")
    audit_identity = value.get("source", {}).get("transport_audit", {})
    audit_path = project_root.resolve() / str(audit_identity.get("path", ""))
    if (
        not audit_path.is_file()
        or _sha256(audit_path.read_bytes()) != audit_identity.get("sha256")
        or audit_path.stat().st_size != audit_identity.get("size_bytes")
    ):
        raise ConvExecplanTransportError("typed transport audit identity differs")
    guarantees = value.get("schema_guarantees", {})
    boundary = value.get("boundary", {})
    if (
        guarantees.get("legacy_integer_params_reused_for_fp32") is not False
        or guarantees.get("requant_cardinality") != "one manifest to many shards"
        or boundary.get("conv_shape_family_parallel_expansion_allowed") is not True
        or boundary.get("whole_network_execplan_generated") is not False
        or boundary.get("hardware_execution_proven") is not False
        or any(boundary.get(field) is not False for field in ("g5_passed", "g6_passed", "g8_passed"))
        or len(value.get("negative_tests", [])) != 7
        or any(item.get("unchanged") is not True for item in value.get("approved_w4_snapshots", []))
    ):
        raise ConvExecplanTransportError("typed transport closure boundary differs")


__all__ = [
    "SCHEMA_VERSION",
    "ConvExecplanTransportError",
    "build_conv_execplan_request",
    "build_conv_execplan_transport_contract",
    "canonical_execplan_bytes",
    "validate_conv_execplan_request",
    "validate_conv_execplan_transport_contract",
]
