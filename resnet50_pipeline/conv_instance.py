from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONV_INSTANCE_SCHEMA_VERSION = "0.1"
FIRST_REAL_CONV_NODE_ID = "node-0004"
GROUP4X7_PROFILE_ID = "w4_group4x7_batch_channel28_candidate_v1"
HIGH4_RING_OWNER_COUNT = 4
GA_LANE_COUNT = 8
TARGET_ALIGNMENT_BYTES = 16

# E0 protects the package already being consumed by the hardware owner.  The
# config, requant manifest and hardware-freeze manifest hashes are immutable.
# The current preflight hash may move only in a reviewed change when its source
# identity changes; the copied hardware-freeze package remains untouched.
FIRST_REAL_CONV_BASELINE_SHA256 = {
    "accumulate_config": "a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c",
    "requant_manifest": "4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f",
    "preflight": "e1143e815a15e51ef97a7a4ea84b260b7081c7949f83173aa06c5e52db7e28a4",
    "hardware_freeze_manifest": "72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550",
}


class ConvInstanceError(ValueError):
    """A typed Conv instance is missing data or contradicts its W3 identity."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvInstanceError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tuple_of_ints(value: Any, *, length: int, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ConvInstanceError(f"{label} must contain {length} integers")
    result = tuple(int(item) for item in value)
    if any(item <= 0 for item in result):
        raise ConvInstanceError(f"{label} dimensions must be positive")
    return result


def _record_by_stage(
    typed: Mapping[str, Any], node_id: str, stage: str
) -> dict[str, Any]:
    records = [
        item
        for item in typed.get("hw_ops", [])
        if item.get("node_id") == node_id and item.get("stage") == stage
    ]
    if len(records) != 1:
        raise ConvInstanceError(
            f"typed contract must contain one {stage} record for {node_id}"
        )
    return records[0]


def _port_by_role(
    record: Mapping[str, Any], direction: str, role: str
) -> dict[str, Any]:
    matches = [
        item
        for item in record.get("ports", {}).get(direction, [])
        if item.get("role") == role
    ]
    if len(matches) != 1:
        raise ConvInstanceError(
            f"{record.get('hw_op_id')} must contain one {direction} port {role}"
        )
    return matches[0]


def _parameter_by_name(record: Mapping[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in record.get("parameters", []) if item.get("name") == name]
    if len(matches) != 1:
        raise ConvInstanceError(
            f"{record.get('hw_op_id')} must contain one parameter {name}"
        )
    return matches[0]


@dataclass(frozen=True)
class ConvTensorBinding:
    port: str
    tensor_id: str
    dtype: str
    shape: tuple[int, ...]
    identity_sha256: str
    identity_source: str
    kind: str
    onnx_name: str | None
    role: str | None = None

    @classmethod
    def from_descriptor(
        cls, port: str, descriptor: Mapping[str, Any]
    ) -> "ConvTensorBinding":
        shape = descriptor.get("shape")
        if not isinstance(shape, list) or not shape:
            raise ConvInstanceError(f"Conv port {port} has no concrete shape")
        tensor_id = descriptor.get("tensor_id")
        dtype = descriptor.get("dtype")
        identity = descriptor.get("identity_sha256")
        if not all(isinstance(item, str) and item for item in (tensor_id, dtype, identity)):
            raise ConvInstanceError(f"Conv port {port} lost typed identity")
        return cls(
            port=port,
            tensor_id=tensor_id,
            dtype=dtype,
            shape=tuple(int(item) for item in shape),
            identity_sha256=identity,
            identity_source=str(descriptor.get("identity_source", "")),
            kind=str(descriptor.get("kind", "")),
            onnx_name=descriptor.get("onnx_name"),
            role=descriptor.get("role"),
        )

    def descriptor(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "tensor_id": self.tensor_id,
            "onnx_name": self.onnx_name,
            "kind": self.kind,
            "shape": list(self.shape),
            "dtype": self.dtype,
            "identity_source": self.identity_source,
            "identity_sha256": self.identity_sha256,
        }
        if self.role is not None:
            value["role"] = self.role
        return value


@dataclass(frozen=True)
class ConvInstanceSpec:
    schema_version: str
    node_id: str
    accumulate_hw_op_id: str
    requant_hw_op_id: str
    onnx_name: str
    onnx_op_type: str
    activation_shape: tuple[int, int, int, int]
    weight_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    kernel: tuple[int, int]
    strides: tuple[int, int]
    pads: tuple[int, int, int, int]
    dilations: tuple[int, int]
    group: int
    tensor_bindings: tuple[ConvTensorBinding, ...]
    parameter_sha256: tuple[tuple[str, str], ...]
    requant_multiplier_sha256: str
    profile_id: str = GROUP4X7_PROFILE_ID
    communication_domain: str = "high4"
    n2n_mem_loop: int = 4
    n2n_src_slice_sel: int = 1
    n2n_dst_slice_sel: int = 1
    n2n_ping_pong: int = 0
    ga_lane_count: int = GA_LANE_COUNT
    alignment_bytes: int = TARGET_ALIGNMENT_BYTES

    @property
    def batch_size(self) -> int:
        return self.activation_shape[0]

    @property
    def input_channels(self) -> int:
        return self.activation_shape[1]

    @property
    def output_channels(self) -> int:
        return self.output_shape[1]

    @property
    def output_height(self) -> int:
        return self.output_shape[2]

    @property
    def output_width(self) -> int:
        return self.output_shape[3]

    @property
    def c_tile(self) -> int:
        return math.ceil(self.input_channels / HIGH4_RING_OWNER_COUNT)

    @property
    def k_tile(self) -> int:
        return math.ceil(self.output_channels / HIGH4_RING_OWNER_COUNT)

    @property
    def first_group_sample_count(self) -> int:
        return 3

    @property
    def first_tile_spatial_count(self) -> int:
        return self.first_group_sample_count * self.output_height * self.output_width

    @property
    def requant_shard_count(self) -> int:
        return math.ceil(self.output_channels / self.ga_lane_count)

    @property
    def requant_shards_per_owner(self) -> int:
        return math.ceil(self.k_tile / self.ga_lane_count)

    def tensor(self, port: str) -> ConvTensorBinding:
        matches = [item for item in self.tensor_bindings if item.port == port]
        if len(matches) != 1:
            raise ConvInstanceError(f"Conv instance has no unique port {port}")
        return matches[0]

    def parameter_hash(self, name: str) -> str:
        matches = [digest for key, digest in self.parameter_sha256 if key == name]
        if len(matches) != 1:
            raise ConvInstanceError(f"Conv instance has no unique parameter {name}")
        return matches[0]

    def validate(self) -> None:
        if self.schema_version != CONV_INSTANCE_SCHEMA_VERSION:
            raise ConvInstanceError("Conv instance schema differs")
        if self.onnx_op_type != "QLinearConv" or self.group != 1:
            raise ConvInstanceError("current Conv instance requires group-1 QLinearConv")
        if self.batch_size != 16:
            raise ConvInstanceError("current RTL28 Conv instance requires batch 16")
        if self.weight_shape[0] != self.output_channels:
            raise ConvInstanceError("Conv output and weight K dimensions differ")
        if self.weight_shape[1] != self.input_channels:
            raise ConvInstanceError("Conv activation and weight C dimensions differ")
        if self.weight_shape[2:] != self.kernel:
            raise ConvInstanceError("Conv kernel and weight shape differ")
        if self.output_shape[0] != self.batch_size:
            raise ConvInstanceError("Conv input/output batch differs")
        if len(self.pads) != 4 or any(item < 0 for item in self.pads):
            raise ConvInstanceError("Conv pads must contain four non-negative integers")
        if self.communication_domain != "high4" or (
            self.n2n_mem_loop,
            self.n2n_src_slice_sel,
            self.n2n_dst_slice_sel,
        ) != (4, 1, 1):
            raise ConvInstanceError("Conv instance lost the reviewed HIGH-4 selector")
        required_ports = {
            "A": ("uint8", self.activation_shape),
            "B": ("int8", self.weight_shape),
            "bias": ("int32", (self.output_channels,)),
            "w_scale": ("float32", (self.output_channels,)),
            "w_zero_point": ("int8", (self.output_channels,)),
            "x_scale": ("float32", (1,)),
            "x_zero_point": ("uint8", (1,)),
            "y_scale": ("float32", (1,)),
            "y_zero_point": ("uint8", (1,)),
            "P": ("int32", self.output_shape),
            "D": ("uint8", self.output_shape),
        }
        if {item.port for item in self.tensor_bindings} != set(required_ports):
            raise ConvInstanceError("Conv instance port coverage differs")
        for port, (dtype, shape) in required_ports.items():
            binding = self.tensor(port)
            if binding.dtype != dtype or binding.shape != shape:
                raise ConvInstanceError(f"Conv port {port} dtype/shape differs")
        if self.k_tile % self.ga_lane_count:
            raise ConvInstanceError("current GA requant path requires an 8-channel K tile")
        if len(self.requant_multiplier_sha256) != 64:
            raise ConvInstanceError("Conv requant multiplier identity differs")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "hw_op_ids": [self.accumulate_hw_op_id, self.requant_hw_op_id],
            "onnx_name": self.onnx_name,
            "onnx_op_type": self.onnx_op_type,
            "geometry": {
                "activation_shape": list(self.activation_shape),
                "weight_shape": list(self.weight_shape),
                "output_shape": list(self.output_shape),
                "kernel": list(self.kernel),
                "strides": list(self.strides),
                "pads": list(self.pads),
                "dilations": list(self.dilations),
                "group": self.group,
            },
            "target": {
                "profile_id": self.profile_id,
                "communication_domain": self.communication_domain,
                "n2n": {
                    "mem_loop": self.n2n_mem_loop,
                    "src_slice_sel": self.n2n_src_slice_sel,
                    "dst_slice_sel": self.n2n_dst_slice_sel,
                    "ping_pong": self.n2n_ping_pong,
                },
                "c_tile": self.c_tile,
                "k_tile": self.k_tile,
                "ga_lane_count": self.ga_lane_count,
                "requant_shard_count": self.requant_shard_count,
            },
            "ports": [item.descriptor() | {"port": item.port} for item in self.tensor_bindings],
            "parameter_sha256": dict(self.parameter_sha256),
            "requant_multiplier_sha256": self.requant_multiplier_sha256,
        }


@dataclass(frozen=True)
class ConvTargetRequest:
    spec: ConvInstanceSpec
    project_root: Path
    accumulate_config_relative: str
    semantic_contract_relative: str
    requant_root_relative: str
    preflight_relative: str
    hardware_freeze_manifest_relative: str
    target_job_name: str

    @property
    def accumulate_config_path(self) -> Path:
        return self.project_root / self.accumulate_config_relative

    @property
    def semantic_contract_path(self) -> Path:
        return self.project_root / self.semantic_contract_relative

    @property
    def requant_root(self) -> Path:
        return self.project_root / self.requant_root_relative

    @property
    def requant_manifest_path(self) -> Path:
        return self.requant_root / "manifest.json"

    @property
    def requant_config_paths(self) -> tuple[Path, ...]:
        return tuple(
            self.requant_root / f"shard-{index:02d}.json"
            for index in range(self.spec.requant_shard_count)
        )

    @property
    def preflight_path(self) -> Path:
        return self.project_root / self.preflight_relative

    @property
    def hardware_freeze_manifest_path(self) -> Path:
        return self.project_root / self.hardware_freeze_manifest_relative

    def validate_checked_in_bindings(self) -> None:
        self.spec.validate()
        required = (
            self.accumulate_config_path,
            self.semantic_contract_path,
            self.requant_manifest_path,
            *self.requant_config_paths,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise ConvInstanceError(f"Conv target request files are missing: {missing}")
        manifest = _load_json(self.requant_manifest_path)
        if (
            manifest.get("node_id") != self.spec.node_id
            or manifest.get("hw_op_id") != self.spec.requant_hw_op_id
            or manifest.get("requant", {}).get("channel_count")
            != self.spec.output_channels
            or manifest.get("coverage", {}).get("shard_count")
            != self.spec.requant_shard_count
        ):
            raise ConvInstanceError("Conv requant manifest is bound to another instance")
        shards = manifest.get("shards", [])
        if len(shards) != len(self.requant_config_paths):
            raise ConvInstanceError("Conv requant config coverage differs")
        for path, shard in zip(self.requant_config_paths, shards, strict=True):
            if _sha256(path) != shard.get("config_sha256"):
                raise ConvInstanceError(f"Conv requant config hash differs: {path}")


def load_conv_instance_spec(project_root: Path, node_id: str) -> ConvInstanceSpec:
    root = project_root.resolve()
    typed = _load_json(root / "contracts" / "typed_config_parameter_contract.json")
    accumulate = _record_by_stage(typed, node_id, "accumulate")
    requant = _record_by_stage(typed, node_id, "requantize")
    if (
        accumulate.get("onnx_op_type") != "QLinearConv"
        or requant.get("onnx_op_type") != "QLinearConv"
        or accumulate.get("hw_op_type") != "ConvInt32Accumulate"
        or requant.get("hw_op_type") != "RequantizeUint8"
    ):
        raise ConvInstanceError(f"{node_id} is not the two-stage QLinearConv lowering")
    accumulate_attributes = accumulate.get("logical_geometry", {}).get("attributes")
    requant_attributes = requant.get("logical_geometry", {}).get("attributes")
    if not isinstance(accumulate_attributes, dict) or accumulate_attributes != requant_attributes:
        raise ConvInstanceError("Conv accumulate/requant attributes differ")

    raw_ports = {
        "A": _port_by_role(accumulate, "inputs", "x"),
        "B": _port_by_role(accumulate, "inputs", "w"),
        "bias": _port_by_role(accumulate, "inputs", "bias"),
        "w_zero_point": _port_by_role(accumulate, "inputs", "w_zero_point"),
        "x_zero_point": _port_by_role(accumulate, "inputs", "x_zero_point"),
        "x_scale": _port_by_role(requant, "inputs", "x_scale"),
        "w_scale": _port_by_role(requant, "inputs", "w_scale"),
        "y_scale": _port_by_role(requant, "inputs", "y_scale"),
        "y_zero_point": _port_by_role(requant, "inputs", "y_zero_point"),
        "P": requant.get("ports", {}).get("inputs", [None])[0],
        "D": requant.get("ports", {}).get("outputs", [None])[0],
    }
    if not all(isinstance(value, dict) for value in raw_ports.values()):
        raise ConvInstanceError("Conv internal/output port descriptors are missing")
    bindings = tuple(
        ConvTensorBinding.from_descriptor(port, raw_ports[port])
        for port in (
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
    )
    direct_parameters = {
        item["name"]: item["value"]["value_sha256"]
        for item in (*accumulate.get("parameters", []), *requant.get("parameters", []))
        if item.get("provenance", {}).get("kind") == "onnx_initializer"
    }
    required_parameters = {
        "bias",
        "w_scale",
        "w_zero_point",
        "x_scale",
        "x_zero_point",
        "y_scale",
        "y_zero_point",
    }
    if set(direct_parameters) != required_parameters:
        raise ConvInstanceError("Conv direct typed parameter coverage differs")

    spec = ConvInstanceSpec(
        schema_version=CONV_INSTANCE_SCHEMA_VERSION,
        node_id=node_id,
        accumulate_hw_op_id=str(accumulate["hw_op_id"]),
        requant_hw_op_id=str(requant["hw_op_id"]),
        onnx_name=str(accumulate["onnx_name"]),
        onnx_op_type="QLinearConv",
        activation_shape=_tuple_of_ints(raw_ports["A"]["shape"], length=4, label="activation_shape"),
        weight_shape=_tuple_of_ints(raw_ports["B"]["shape"], length=4, label="weight_shape"),
        output_shape=_tuple_of_ints(raw_ports["D"]["shape"], length=4, label="output_shape"),
        kernel=_tuple_of_ints(accumulate_attributes["kernel_shape"], length=2, label="kernel"),
        strides=_tuple_of_ints(accumulate_attributes["strides"], length=2, label="strides"),
        pads=tuple(int(item) for item in accumulate_attributes["pads"]),
        dilations=_tuple_of_ints(accumulate_attributes["dilations"], length=2, label="dilations"),
        group=int(accumulate_attributes["group"]),
        tensor_bindings=bindings,
        parameter_sha256=tuple(sorted(direct_parameters.items())),
        requant_multiplier_sha256=str(
            _parameter_by_name(requant, "requant_multiplier")["value"]["value_sha256"]
        ),
    )
    spec.validate()
    return spec


def make_conv_target_request(
    project_root: Path, node_id: str = FIRST_REAL_CONV_NODE_ID
) -> ConvTargetRequest:
    root = project_root.resolve()
    spec = load_conv_instance_spec(root, node_id)
    if node_id == FIRST_REAL_CONV_NODE_ID:
        return ConvTargetRequest(
            spec=spec,
            project_root=root,
            accumulate_config_relative="conv_1x1_real.json",
            semantic_contract_relative="contracts/conv_1x1_lc_pe_stream_semantics.json",
            requant_root_relative="conv_1x1_requant_real",
            preflight_relative="artifacts/w5/hwop-0004-00/preflight.json",
            hardware_freeze_manifest_relative=(
                "artifacts/w5/hwop-0004-00/hardware_freeze/manifest.json"
            ),
            target_job_name="hwop-0004_target_config_full",
        )
    config_root = f"configs/conv/{spec.accumulate_hw_op_id}"
    return ConvTargetRequest(
        spec=spec,
        project_root=root,
        accumulate_config_relative=f"{config_root}/accumulate.json",
        semantic_contract_relative=f"{config_root}/semantics.json",
        requant_root_relative=f"{config_root}/requant",
        preflight_relative=f"artifacts/w5/{spec.accumulate_hw_op_id}/preflight.json",
        hardware_freeze_manifest_relative=(
            f"artifacts/w5/{spec.accumulate_hw_op_id}/hardware_freeze/manifest.json"
        ),
        target_job_name=(
            f"{spec.accumulate_hw_op_id.removesuffix('-00')}_target_config_full"
        ),
    )


def build_conv_target_request(
    project_root: Path, node_id: str = FIRST_REAL_CONV_NODE_ID
) -> ConvTargetRequest:
    request = make_conv_target_request(project_root, node_id)
    request.validate_checked_in_bindings()
    return request


def assert_first_real_conv_baseline(project_root: Path) -> None:
    request = build_conv_target_request(project_root, FIRST_REAL_CONV_NODE_ID)
    observed = {
        "accumulate_config": _sha256(request.accumulate_config_path),
        "requant_manifest": _sha256(request.requant_manifest_path),
        "preflight": _sha256(request.preflight_path),
        "hardware_freeze_manifest": _sha256(request.hardware_freeze_manifest_path),
    }
    if observed != FIRST_REAL_CONV_BASELINE_SHA256:
        raise ConvInstanceError(
            f"first real Conv frozen bytes changed: expected={FIRST_REAL_CONV_BASELINE_SHA256}, "
            f"observed={observed}"
        )


__all__ = [
    "CONV_INSTANCE_SCHEMA_VERSION",
    "ConvInstanceError",
    "ConvInstanceSpec",
    "ConvTargetRequest",
    "FIRST_REAL_CONV_BASELINE_SHA256",
    "FIRST_REAL_CONV_NODE_ID",
    "assert_first_real_conv_baseline",
    "build_conv_target_request",
    "load_conv_instance_spec",
    "make_conv_target_request",
]
