from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from resnet50_pipeline.conv_sa_contract import validate_first_conv_sa_contract


CONV_INSTANCE_SCHEMA_VERSION = "0.1"
CONV_TRANSPORT_ABI_LEGACY = "conv_sa_legacy_v1"
CONV_TRANSPORT_ABI_Q8K8 = "conv_sa_q8k8_v2"
CONV_TRANSPORT_ABIS = frozenset(
    {CONV_TRANSPORT_ABI_LEGACY, CONV_TRANSPORT_ABI_Q8K8}
)
FIRST_REAL_CONV_NODE_ID = "node-0004"
GROUP4X7_PROFILE_ID = "w4_group4x7_batch_channel28_candidate_v1"
HIGH4_RING_OWNER_COUNT = 4
GA_LANE_COUNT = 8
TARGET_ALIGNMENT_BYTES = 16
BUFFER5_PRODUCER_PORT = {"special_array": 0, "general_array": 1}
BUFFER5_PRODUCER_LABEL = {"special_array": "SpecArray", "general_array": "GeneArray"}
CONV_GEMM_SA_OUTPORT_JSON_MODE = "col"
CONV_GEMM_SA_OUTPORT_RTL_MAJOR = 0
SA_ONLY_CONFIG_MASK = "11101110"

# E0 protects the package already being consumed by the hardware owner.  The
# config, requant manifest and hardware-freeze manifest hashes are immutable.
# The current preflight hash may move only in a reviewed change when its source
# identity changes; the copied hardware-freeze package remains untouched.
FIRST_REAL_CONV_V1_BASELINE_SHA256 = {
    "accumulate_config": "a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c",
    "requant_manifest": "4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f",
    "preflight": "dff41e18e324d109257bb4f4d425ec251448c98efc526a987c243dfe779c5f46",
    "hardware_freeze_manifest": "72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550",
}

# Backward-compatible name for the immutable hardware-owner v1 handoff.  The
# repaired v4 identity is deliberately separate instead of rewriting v1/v3.
FIRST_REAL_CONV_BASELINE_SHA256 = FIRST_REAL_CONV_V1_BASELINE_SHA256
FIRST_REAL_CONV_V4_BASELINE_SHA256 = {
    "accumulate_config": "8535fd06afbdc8ff3ea26f0ec64c179c3fda853a3ebe0b9824720fc9fa10b8be",
    "semantic_contract": "e6765dad4c0b693f1968c062aefa34078c99f01eff83a6c434cec0a9d4fb21e2",
    "execplan_request": "eb2609c456f416cb9c92f1268749b7daf23866e0c1421b0e01b3857d3d9c3fb4",
    "preflight": "796163961d0903516c35db25cbd36de50fb86ff7a10cb8e9d47d16ac9d00c40a",
    "hardware_freeze_manifest": "651c764b2aab6cb9d985ca9a631587aac6e9fe4d8fef04a600132c324dfd1a2f",
    "hardware_execplan_manifest": "48bfe832c7c19392c05b088f060467d02a90c814e48a225620bcfd108be0bd01",
}
FIRST_REAL_CONV_V5_BASELINE_SHA256 = {
    "accumulate_config": "6fbae16126e8aa88b66de72c875be71a5384de4980bbb45551a50cea09f2c774",
    "semantic_contract": "79da43007216569036270bc99effb96edab5d190e59292461f8270cc589905c0",
    "execplan_request": "877aa9956d4e823cff891e8c5186f99fcd204b714bdbf58b347b5229f310307d",
    "preflight": "256e75a28a95901b90b9362c0c5613844d8b35a9fb69af04d1fcc81ff085632a",
    "hardware_freeze_manifest": "4a5fc6cc27ff3e066e1d0fa2a6d0e62147fdf98d9e304e7922ce8215a479a8ff",
    "hardware_execplan_manifest": "d6dcc017b4652ac22d0f68ed7933286a54be3ebefbd8cf28ebc623679ad39f0e",
}
FIRST_REAL_CONV_V6_BASELINE_SHA256 = {
    "accumulate_config": "b3786d66019a02415d40fc0f9dccce17005dbac1d86185e1ab3fe4cbce86472f",
    "semantic_contract": "deb084c080dfb7ac63f130126b665dcc76a1c2fc5a27903ae61d4ccddf513b22",
    "execplan_request": "6243ac3c9a0a791eb03dbff2b3ae40ae0bc5a1ca58545235fd80f6f5ac203cc9",
    "preflight": "802b400d5989d7340ebadbe784b835da0bdaff4bba26b9cfc32f6f4b35c84ee0",
    "hardware_freeze_manifest": "6149468eb897f90e6868b8148bfd1b2d36a88ec804da74a4c178748366bd255b",
    "hardware_execplan_manifest": "e42c894922f2ed14112ed56d066802ce8e522a6c6f1e35c02ec50b13d8434090",
}
FIRST_REAL_CONV_V8_BASELINE_SHA256 = {
    "accumulate_config": "ee7590ef29fb3972b3c63adb73c0cb86efd0dc6674c45742b59dc21b8eefbef1",
    "semantic_contract": "87cb2b0097e59f89cec42e43dbb860e87108875418e4caf8dd25cd54b3ea22f8",
    "execplan_request": "0a273ea733b2e89cca708fb274820998f69e0ff934fdefb27c94fcd90ed615b9",
    "preflight": "43c8968a405a6ad0a0ca9dcb1dd097d09076bbe9e669f2c07edbd78c3c3426b1",
    "hardware_freeze_manifest": "fde92b3abd37f1ea6ffd482dd4202dfb87312ed2d57d7ae3deeaa22e78660ba0",
    "hardware_execplan_manifest": "0796802938eade0e32c99e79e4169a94823d90820216b6d29f1515466eb93375",
}
FIRST_REAL_CONV_V9_STATIC_SHA256 = {
    "accumulate_config": "e3cb41c76a8e476067822e6edebf483c3f4c54c2eae18c9f1c016466ea310287",
    "semantic_contract": "94c973fc52cf749a6ba35547ef3966a1fcc869dc82049ed666e2594f3da53981",
    "execplan_request": "25ed6994e70401b175e9f796ba505bf1359acf5e27c620395d6183e028855f9d",
    "preflight": "219decd86f6eacf0308b1e08da6c1a709644099a257d2b6215cd2ce9e97f1753",
    "hardware_freeze_manifest": "5f4eda550257be64e25c9d78e4c1d6e3066604c4bb3860ed4d2ffc375c3ad162",
    "hardware_execplan_manifest": "f9cfc7a021d54ac9bf700097bc040cc0e06cc0d55fe0dcf0cc448fe78c7009d9",
    "server_overlay_zip": "a5dd6c1184190162f5810a242adbcbb8a9e773b5731217ca4a6e983c617e7517",
}


class ConvInstanceError(ValueError):
    """A typed Conv instance is missing data or contradicts its W3 identity."""


def validate_buffer5_output_route(
    config: Mapping[str, Any], *, expected_producer: str
) -> None:
    """Require buffer5 to select a present, stage-declared array producer."""

    if expected_producer not in BUFFER5_PRODUCER_PORT:
        raise ConvInstanceError(
            f"unsupported buffer5 producer invariant: {expected_producer}"
        )
    buffers = config.get("buffer_config")
    if not isinstance(buffers, Mapping):
        raise ConvInstanceError("target config buffer_config is missing")
    buffer5 = buffers.get("buffer5")
    if not isinstance(buffer5, Mapping):
        raise ConvInstanceError("target config buffer5 is missing")
    route = buffer5.get("dst_port")
    if type(route) is not int or route not in (0, 1):
        raise ConvInstanceError("buffer5.dst_port must be the integer 0 or 1")
    expected_port = BUFFER5_PRODUCER_PORT[expected_producer]
    expected_label = BUFFER5_PRODUCER_LABEL[expected_producer]
    if route != expected_port:
        raise ConvInstanceError(
            f"buffer5.dst_port must be {expected_port} ({expected_label} producer)"
        )
    selected = config.get(expected_producer)
    if not isinstance(selected, Mapping):
        raise ConvInstanceError(
            f"buffer5 selects {expected_label}, but {expected_producer} is absent"
        )


def validate_conv_accumulate_output_route(config: Mapping[str, Any]) -> None:
    """Require the reviewed SA-only Conv output path and RTL row-major bit."""

    special = config.get("special_array")
    general = config.get("general_array")
    if not isinstance(special, Mapping) or general is not None:
        raise ConvInstanceError(
            "Conv accumulate output-route invariant requires an SA-only program"
        )
    validate_buffer5_output_route(config, expected_producer="special_array")
    if special.get("mode") != "gemm":
        raise ConvInstanceError("Conv accumulate SpecialArray mode must be gemm")
    outport = special.get("outport")
    if not isinstance(outport, Mapping):
        raise ConvInstanceError("Conv accumulate SpecialArray outport is missing")
    mode = outport.get("mode")
    if mode != CONV_GEMM_SA_OUTPORT_JSON_MODE:
        raise ConvInstanceError(
            "Conv GEMM SpecialArray outport must use JSON mode "
            f"{CONV_GEMM_SA_OUTPORT_JSON_MODE!r}, which the official encoder "
            f"maps to RTL sa_outport_major={CONV_GEMM_SA_OUTPORT_RTL_MAJOR} "
            "(row-major)"
        )


def validate_conv_accumulate_config_mask(config: Mapping[str, Any]) -> None:
    """Require the reference-compatible presence mask for an SA-only Conv."""

    mask = config.get("CONFIG")
    if mask != SA_ONLY_CONFIG_MASK:
        raise ConvInstanceError(
            "SA-only Conv CONFIG must be "
            f"{SA_ONLY_CONFIG_MASK}; observed {mask!r}"
        )


def validate_conv_accumulate_neighbor_ring(
    config: Mapping[str, Any],
    *,
    expected_group_size: int,
) -> None:
    """Require the NSE buffer pair and NRM terminal count for a HIGH-N ring."""

    if (
        isinstance(expected_group_size, bool)
        or not isinstance(expected_group_size, int)
        or not 2 <= expected_group_size <= 32
    ):
        raise ConvInstanceError(
            "expected neighbor group size must be an integer in [2, 32]"
        )

    n2n = config.get("n2n")
    buffers = config.get("buffer_config")
    if not isinstance(n2n, Mapping) or not n2n:
        raise ConvInstanceError(
            "Conv accumulate config must define at least one neighbor stream"
        )
    if not isinstance(buffers, Mapping):
        raise ConvInstanceError("Conv accumulate config must define buffer_config")

    terminal_count = expected_group_size - 1
    for stream_name, stream_config in n2n.items():
        match = re.fullmatch(r"neighbor_stream([0-2])", str(stream_name))
        if match is None or not isinstance(stream_config, Mapping):
            raise ConvInstanceError(
                f"unsupported Conv neighbor stream binding: {stream_name!r}"
            )
        stream_index = int(match.group(1))
        mem_loop = stream_config.get("mem_loop")
        if (
            isinstance(mem_loop, bool)
            or not isinstance(mem_loop, int)
            or mem_loop != expected_group_size
        ):
            raise ConvInstanceError(
                f"{stream_name}.mem_loop must equal HIGH group size "
                f"{expected_group_size}; observed {mem_loop!r}"
            )

        for buffer_index in (2 * stream_index, 2 * stream_index + 1):
            buffer_name = f"buffer{buffer_index}"
            buffer_config = buffers.get(buffer_name)
            if not isinstance(buffer_config, Mapping):
                raise ConvInstanceError(f"{stream_name} requires {buffer_name}")
            nbr_enable = buffer_config.get("nbr_enable")
            if (
                isinstance(nbr_enable, bool)
                or not isinstance(nbr_enable, int)
                or nbr_enable != 1
            ):
                raise ConvInstanceError(
                    f"{buffer_name}.nbr_enable must be 1 for {stream_name}; "
                    f"observed {nbr_enable!r}"
                )
            nbr_count = buffer_config.get("buffer_nbr_cnt")
            if (
                isinstance(nbr_count, bool)
                or not isinstance(nbr_count, int)
                or nbr_count != terminal_count
            ):
                raise ConvInstanceError(
                    f"{buffer_name}.buffer_nbr_cnt must equal HIGH group size - 1 "
                    f"({terminal_count}); observed {nbr_count!r}"
                )


def validate_conv_requant_output_route(config: Mapping[str, Any]) -> None:
    """Require a GA-only Conv requant program to write buffer5 from GA."""

    special = config.get("special_array")
    general = config.get("general_array")
    if special is not None or not isinstance(general, Mapping):
        raise ConvInstanceError(
            "Conv requant output-route invariant requires a GA-only program"
        )
    validate_buffer5_output_route(config, expected_producer="general_array")


def audit_generated_conv_output_routes(project_root: Path) -> dict[str, Any]:
    """Audit every mutable project-generated Conv config, excluding frozen history."""

    root = project_root.resolve()
    accumulate_paths = [root / "conv_full.json", root / "conv_1x1_real.json"]
    accumulate_paths.extend(sorted((root / "configs" / "conv").glob("*/accumulate.json")))
    requant_paths = sorted((root / "conv_1x1_requant_real").glob("shard-*.json"))
    requant_paths.extend(
        sorted((root / "configs" / "conv").glob("*/requant/shard-*.json"))
    )
    records: list[dict[str, Any]] = []
    for stage, paths, validator in (
        ("accumulate", accumulate_paths, validate_conv_accumulate_output_route),
        ("requant", requant_paths, validate_conv_requant_output_route),
    ):
        for path in paths:
            if not path.is_file():
                raise ConvInstanceError(f"generated Conv route-audit file is missing: {path}")
            config = _load_json(path)
            validator(config)
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "stage": stage,
                    "buffer5_dst_port": config["buffer_config"]["buffer5"]["dst_port"],
                    "sa_outport_json_mode": (
                        config["special_array"]["outport"]["mode"]
                        if stage == "accumulate"
                        else None
                    ),
                    "sha256": _sha256(path),
                }
            )
    return {
        "status": "generated_conv_output_routes_passed",
        "accumulate_config_count": len(accumulate_paths),
        "requant_config_count": len(requant_paths),
        "config_count": len(records),
        "historical_freezes_excluded": True,
        "configs": records,
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvInstanceError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _embedded_artifact_sha256(
    request_path: Path, *, operator_index: int, role: str
) -> str:
    request = _load_json(request_path)
    operators = request.get("operators")
    if not isinstance(operators, list) or len(operators) <= operator_index:
        raise ConvInstanceError(f"typed request has no operator {operator_index}: {request_path}")
    artifacts = operators[operator_index].get("config_artifacts")
    matches = [
        item
        for item in artifacts if item.get("role") == role
    ] if isinstance(artifacts, list) else []
    if len(matches) != 1 or not isinstance(matches[0].get("sha256"), str):
        raise ConvInstanceError(
            f"typed request has no unique {role} artifact: {request_path}"
        )
    return matches[0]["sha256"]


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
    transport_abi: str | None
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
    def requant_encoder_contract_path(self) -> Path:
        return self.requant_root / "encoder_contract.json"

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
        if self.spec.node_id == FIRST_REAL_CONV_NODE_ID:
            required = (*required, self.requant_encoder_contract_path)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise ConvInstanceError(f"Conv target request files are missing: {missing}")
        accumulate_config = _load_json(self.accumulate_config_path)
        semantic_contract = _load_json(self.semantic_contract_path)
        if (
            self.transport_abi not in CONV_TRANSPORT_ABIS
            or semantic_contract.get("transport_abi") != self.transport_abi
        ):
            raise ConvInstanceError("Conv semantic contract transport ABI differs")
        validate_conv_accumulate_output_route(accumulate_config)
        # Existing candidate instances remain frozen until node-0004 passes
        # hardware.  The active first-operator entry and every newly generated
        # config are fail-closed on the reference SA-only presence mask.
        if self.spec.node_id == FIRST_REAL_CONV_NODE_ID:
            validate_conv_accumulate_config_mask(accumulate_config)
            validate_conv_accumulate_neighbor_ring(
                accumulate_config,
                expected_group_size=self.spec.n2n_mem_loop,
            )
            validate_first_conv_sa_contract(accumulate_config)
        for path in self.requant_config_paths:
            validate_conv_requant_output_route(_load_json(path))
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
        if self.spec.node_id == FIRST_REAL_CONV_NODE_ID:
            encoder_contract = _load_json(self.requant_encoder_contract_path)
            records = encoder_contract.get("records")
            if (
                encoder_contract.get("schema_version")
                != "resnet50-conv-requant-encoder-contract-0.1"
                or encoder_contract.get("status")
                != "official_encoder_double_run_bound"
                or encoder_contract.get("node_id") != self.spec.node_id
                or encoder_contract.get("hw_op_id") != self.spec.requant_hw_op_id
                or not isinstance(records, list)
                or int(encoder_contract.get("record_count", -1))
                != self.spec.requant_shard_count
                or len(records) != self.spec.requant_shard_count
            ):
                raise ConvInstanceError(
                    "Conv requant encoder contract is bound to another instance"
                )
            for shard_index, (path, record) in enumerate(
                zip(self.requant_config_paths, records, strict=True)
            ):
                config = record.get("config") if isinstance(record, dict) else None
                official = (
                    record.get("official_encoder")
                    if isinstance(record, dict)
                    else None
                )
                if (
                    not isinstance(record, dict)
                    or record.get("shard_index") != shard_index
                    or record.get("binding_id")
                    != f"{self.spec.requant_hw_op_id}.shard-{shard_index:02d}"
                    or record.get("repeat_outputs_identical") is not True
                    or not isinstance(config, dict)
                    or config.get("sha256") != _sha256(path)
                    or not isinstance(official, dict)
                    or not isinstance(official.get("modules_dump_128b.bin"), dict)
                ):
                    raise ConvInstanceError(
                        f"Conv requant encoder binding differs: shard-{shard_index:02d}"
                    )


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
        semantic_contract_relative = (
            "contracts/conv_1x1_lc_pe_stream_semantics.json"
        )
        semantic_contract_path = root / semantic_contract_relative
        transport_abi = (
            _load_json(semantic_contract_path).get("transport_abi")
            if semantic_contract_path.is_file()
            else None
        )
        if transport_abi is not None and transport_abi not in CONV_TRANSPORT_ABIS:
            raise ConvInstanceError("Conv semantic contract transport ABI is missing or unknown")
        return ConvTargetRequest(
            spec=spec,
            project_root=root,
            transport_abi=transport_abi,
            accumulate_config_relative="conv_1x1_real.json",
            semantic_contract_relative=semantic_contract_relative,
            requant_root_relative="conv_1x1_requant_real",
            preflight_relative="artifacts/w5/hwop-0004-00/v19/preflight.json",
            hardware_freeze_manifest_relative=(
                "artifacts/w5/hwop-0004-00/v19/hardware_freeze/manifest.json"
            ),
            target_job_name="hwop-0004_target_config_full",
        )
    config_root = f"configs/conv/{spec.accumulate_hw_op_id}"
    semantic_contract_relative = f"{config_root}/semantics.json"
    semantic_contract_path = root / semantic_contract_relative
    transport_abi = (
        _load_json(semantic_contract_path).get("transport_abi")
        if semantic_contract_path.is_file()
        else None
    )
    if transport_abi is not None and transport_abi not in CONV_TRANSPORT_ABIS:
        raise ConvInstanceError("Conv semantic contract transport ABI is missing or unknown")
    return ConvTargetRequest(
        spec=spec,
        project_root=root,
        transport_abi=transport_abi,
        accumulate_config_relative=f"{config_root}/accumulate.json",
        semantic_contract_relative=semantic_contract_relative,
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
    root = project_root.resolve()
    observed_v1 = {
        "accumulate_config": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze/configs/conv_1x1_real.json"
        ),
        "requant_manifest": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze/configs/requant/manifest.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze/manifest.json"
        ),
    }
    if observed_v1 != FIRST_REAL_CONV_V1_BASELINE_SHA256:
        raise ConvInstanceError(
            "first real Conv v1 frozen bytes changed: "
            f"expected={FIRST_REAL_CONV_V1_BASELINE_SHA256}, observed={observed_v1}"
        )
    observed_v4 = {
        "accumulate_config": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v4/configs/conv_1x1_real.json"
        ),
        "semantic_contract": _embedded_artifact_sha256(
            root / "artifacts/w5/hwop-0004-00/v4/execplan_request.json",
            operator_index=0,
            role="semantic_contract",
        ),
        "execplan_request": _sha256(
            root / "artifacts/w5/hwop-0004-00/v4/execplan_request.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/v4/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze_v4/manifest.json"
        ),
        "hardware_execplan_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v4/manifest.json"
        ),
    }
    if observed_v4 != FIRST_REAL_CONV_V4_BASELINE_SHA256:
        raise ConvInstanceError(
            "first real Conv v4 bytes changed: "
            f"expected={FIRST_REAL_CONV_V4_BASELINE_SHA256}, observed={observed_v4}"
        )
    observed_v5 = {
        "accumulate_config": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v5/configs/conv_1x1_real.json"
        ),
        "semantic_contract": _embedded_artifact_sha256(
            root / "artifacts/w5/hwop-0004-00/v5/execplan_request.json",
            operator_index=0,
            role="semantic_contract",
        ),
        "execplan_request": _sha256(
            root / "artifacts/w5/hwop-0004-00/v5/execplan_request.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/v5/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze_v5/manifest.json"
        ),
        "hardware_execplan_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v5/manifest.json"
        ),
    }
    if observed_v5 != FIRST_REAL_CONV_V5_BASELINE_SHA256:
        raise ConvInstanceError(
            "first real Conv v5 bytes changed: "
            f"expected={FIRST_REAL_CONV_V5_BASELINE_SHA256}, observed={observed_v5}"
        )
    observed_v6 = {
        "accumulate_config": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/configs/conv_1x1_real.json"
        ),
        "semantic_contract": _embedded_artifact_sha256(
            root / "artifacts/w5/hwop-0004-00/v6/execplan_request.json",
            operator_index=0,
            role="semantic_contract",
        ),
        "execplan_request": _sha256(
            root / "artifacts/w5/hwop-0004-00/v6/execplan_request.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/v6/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/manifest.json"
        ),
        "hardware_execplan_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v6/manifest.json"
        ),
    }
    if observed_v6 != FIRST_REAL_CONV_V6_BASELINE_SHA256:
        raise ConvInstanceError(
            "first real Conv v6 bytes changed: "
            f"expected={FIRST_REAL_CONV_V6_BASELINE_SHA256}, observed={observed_v6}"
        )
    observed_v8 = {
        "accumulate_config": _sha256(
            root
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v8/configs/conv_1x1_real.json"
        ),
        "semantic_contract": _embedded_artifact_sha256(
            root / "artifacts/w5/hwop-0004-00/v8/execplan_request.json",
            operator_index=0,
            role="semantic_contract",
        ),
        "execplan_request": _sha256(
            root / "artifacts/w5/hwop-0004-00/v8/execplan_request.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/v8/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze_v8/manifest.json"
        ),
        "hardware_execplan_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v8/manifest.json"
        ),
    }
    if observed_v8 != FIRST_REAL_CONV_V8_BASELINE_SHA256:
        raise ConvInstanceError(
            "first real Conv v8 bytes changed: "
            f"expected={FIRST_REAL_CONV_V8_BASELINE_SHA256}, observed={observed_v8}"
        )
    observed_v9 = {
        "accumulate_config": _sha256(root / "conv_1x1_real.json"),
        "semantic_contract": _embedded_artifact_sha256(
            root / "artifacts/w5/hwop-0004-00/v9/execplan_request.json",
            operator_index=0,
            role="semantic_contract",
        ),
        "execplan_request": _sha256(
            root / "artifacts/w5/hwop-0004-00/v9/execplan_request.json"
        ),
        "preflight": _sha256(root / "artifacts/w5/hwop-0004-00/v9/preflight.json"),
        "hardware_freeze_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_freeze_v9/manifest.json"
        ),
        "hardware_execplan_manifest": _sha256(
            root / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v9/manifest.json"
        ),
        "server_overlay_zip": _sha256(
            root / "artifacts/w5/hwop-0004-00/server_overlay_v9.zip"
        ),
    }
    if observed_v9 != FIRST_REAL_CONV_V9_STATIC_SHA256:
        raise ConvInstanceError(
            "first real Conv v9 static package bytes changed: "
            f"expected={FIRST_REAL_CONV_V9_STATIC_SHA256}, observed={observed_v9}"
        )


__all__ = [
    "CONV_INSTANCE_SCHEMA_VERSION",
    "CONV_TRANSPORT_ABI_LEGACY",
    "CONV_TRANSPORT_ABI_Q8K8",
    "BUFFER5_PRODUCER_PORT",
    "CONV_GEMM_SA_OUTPORT_JSON_MODE",
    "CONV_GEMM_SA_OUTPORT_RTL_MAJOR",
    "SA_ONLY_CONFIG_MASK",
    "ConvInstanceError",
    "ConvInstanceSpec",
    "ConvTargetRequest",
    "FIRST_REAL_CONV_BASELINE_SHA256",
    "FIRST_REAL_CONV_V9_STATIC_SHA256",
    "FIRST_REAL_CONV_NODE_ID",
    "FIRST_REAL_CONV_V1_BASELINE_SHA256",
    "FIRST_REAL_CONV_V4_BASELINE_SHA256",
    "FIRST_REAL_CONV_V5_BASELINE_SHA256",
    "FIRST_REAL_CONV_V6_BASELINE_SHA256",
    "FIRST_REAL_CONV_V8_BASELINE_SHA256",
    "validate_conv_accumulate_output_route",
    "validate_conv_accumulate_config_mask",
    "validate_conv_accumulate_neighbor_ring",
    "validate_buffer5_output_route",
    "validate_conv_requant_output_route",
    "audit_generated_conv_output_routes",
    "assert_first_real_conv_baseline",
    "build_conv_target_request",
    "load_conv_instance_spec",
    "make_conv_target_request",
]
