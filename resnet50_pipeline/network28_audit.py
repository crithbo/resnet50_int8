"""RTL28 W4 whole-network physical compatibility and static-cost audit.

The audit consumes only the small W3 graph catalog.  It never reads golden
tensor payloads, emits W5 configuration, or claims target timing/hardware
approval.  Two executable candidate schedules are covered: group4x7 for the
whole graph, and one permitted group4x7-to-global transition at the UINT8
Quantize-to-MatMul head boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any

import numpy as np

from .add28_layout import ADD28_LAYOUT_IDS, QLinearAddPhysicalLayout
from .conv28_layout import CONV28_LAYOUT_IDS, QLinearConvPhysicalLayout
from .memory import TARGET_DRAM_GEOMETRY28
from .matmul28_layout import MATMUL28_LAYOUT_IDS, QLinearMatMulPhysicalLayout
from .pool28_layout import (
    GLOBAL_AVERAGE_POOL_LAYOUT_IDS,
    MAXPOOL_LAYOUT_IDS,
    GlobalAveragePoolPhysicalLayout,
    MaxPoolPhysicalLayout,
)
from .profile28 import (
    BATCH_SIZE,
    GROUP_SAMPLE_COUNTS,
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    Profile28Schedule,
    ProfileTransition,
    TransitionBoundary,
    group_to_sample_range,
)
from .simple_layout import SIMPLE_LAYOUT_IDS, VIEW_LAYOUT_IDS
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


ALIGNMENT = 16
GROUP_ONLY_SCENARIO = "group4x7_only"
GLOBAL_HEAD_SCENARIO = "group4x7_to_global_head"
SCENARIO_IDS = (GROUP_ONLY_SCENARIO, GLOBAL_HEAD_SCENARIO)
PHYSICAL_SIGNATURE_FIELDS = (
    "logical_shape",
    "dtype",
    "profile_id",
    "partition_policy",
    "feature_tile",
    "storage_sample_count",
    "canonical_physical_shape",
    "payload_bytes_per_slice",
    "aligned_bytes_per_slice",
    "tail_semantic",
    "byte_order",
    "alignment_bytes",
    "owner_order",
    "slice_regions",
)


def _align(value: int, alignment: int = ALIGNMENT) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _shape(tensor: dict[str, Any]) -> tuple[int, ...]:
    values = tuple(
        BATCH_SIZE if value == "N" else int(value) for value in tensor["shape"]
    )
    if not values or any(value <= 0 for value in values):
        raise ValueError(f"invalid formal tensor shape: {tensor['shape']!r}")
    return values


def _logical_bytes(tensor: dict[str, Any]) -> int:
    return math.prod(_shape(tensor)) * np.dtype(tensor["dtype"]).itemsize


def _canonical_physical_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    if len(shape) < 2:
        return shape
    return (shape[0], *(value for value in shape[1:-1] if value != 1), shape[-1])


def _feature_spec(tensor: dict[str, Any], profile_id: str) -> dict[str, Any]:
    logical_shape = _shape(tensor)
    if len(logical_shape) not in {2, 4} or logical_shape[0] != BATCH_SIZE:
        raise ValueError(
            f"RTL28 runtime feature tensor must be rank-2/rank-4 batch16: {logical_shape}"
        )
    owner_count = 4 if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else 28
    storage_samples = (
        max(GROUP_SAMPLE_COUNTS)
        if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
        else BATCH_SIZE
    )
    feature_tile = math.ceil(logical_shape[1] / owner_count)
    physical_shape = (storage_samples, *logical_shape[2:], feature_tile)
    payload_bytes = math.prod(physical_shape) * np.dtype(tensor["dtype"]).itemsize
    return {
        "logical_shape": logical_shape,
        "dtype": tensor["dtype"],
        "physical_shape": physical_shape,
        "canonical_physical_shape": _canonical_physical_shape(physical_shape),
        "payload_bytes": payload_bytes,
        "aligned_bytes": _align(payload_bytes),
        "feature_tile": feature_tile,
        "storage_sample_count": storage_samples,
        "physical_axis_order": "N-spatial-F-local",
    }


def _scalar_spec(tensor: dict[str, Any]) -> dict[str, Any]:
    shape = _shape(tensor)
    payload_bytes = _logical_bytes(tensor)
    return {
        "logical_shape": shape,
        "dtype": tensor["dtype"],
        "physical_shape": shape,
        "canonical_physical_shape": shape,
        "payload_bytes": payload_bytes,
        "aligned_bytes": _align(payload_bytes),
        "feature_tile": None,
        "storage_sample_count": BATCH_SIZE,
        "physical_axis_order": "replicated-scalar",
    }


def _layout_id(op_type: str, profile_id: str) -> str:
    if op_type in {"QuantizeLinear", "DequantizeLinear"}:
        return SIMPLE_LAYOUT_IDS[profile_id]
    if op_type == "Flatten":
        return VIEW_LAYOUT_IDS[profile_id]
    if op_type == "QLinearConv":
        return CONV28_LAYOUT_IDS[profile_id]
    if op_type == "MaxPool":
        return MAXPOOL_LAYOUT_IDS[profile_id]
    if op_type == "QLinearAdd":
        return ADD28_LAYOUT_IDS[profile_id]
    if op_type == "QLinearGlobalAveragePool":
        return GLOBAL_AVERAGE_POOL_LAYOUT_IDS[profile_id]
    if op_type == "QLinearMatMul":
        return MATMUL28_LAYOUT_IDS[profile_id]
    raise ValueError(f"no RTL28 layout for {op_type}")


def _plan_node(
    node: dict[str, Any],
    tensors: dict[str, dict[str, Any]],
    profile_id: str,
) -> dict[str, Any]:
    inputs = node["input_tensor_ids"]
    outputs = node["output_tensor_ids"]
    attrs = node["attributes"]
    op_type = node["op_type"]
    ports: dict[str, dict[str, Any]]
    raw_sizes: dict[str, int]
    internal_int32 = 0
    ring_hop_bytes = 0
    weight_physical = 0
    weight_group_replication = 0
    broadcast_group_replication = 0

    if op_type == "QLinearConv":
        layout = QLinearConvPhysicalLayout(profile_id)
        plan = layout.plan(
            activation_shape=_shape(tensors[inputs[0]]),
            weight_shape=_shape(tensors[inputs[3]]),
            strides=tuple(attrs.get("strides", (1, 1))),
            pads=tuple(attrs.get("pads", (0, 0, 0, 0))),
            dilations=tuple(attrs.get("dilations", (1, 1))),
            group=int(attrs.get("group", 1)),
        )
        ports = {
            item.port: {
                "logical_shape": item.logical_shape,
                "dtype": item.dtype,
                "physical_shape": item.physical_shape,
                "canonical_physical_shape": _canonical_physical_shape(
                    item.physical_shape
                ),
                "payload_bytes": item.payload_bytes,
                "aligned_bytes": _align(item.payload_bytes),
                "feature_tile": (
                    plan.c_tile if item.port == "A" else plan.k_tile
                    if item.port in {"P", "D"}
                    else None
                ),
                "storage_sample_count": plan.storage_sample_count,
                "physical_axis_order": item.physical_axis_order,
            }
            for item in plan.ports
        }
        raw_sizes = {item.port: item.payload_bytes for item in plan.ports}
        used_bytes = plan.per_slice_used_bytes
        capacity = plan.per_slice_capacity_bytes
        internal_int32 = raw_sizes["P"] * 28
        owner_count = 4 if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else 28
        ring_hop_bytes = raw_sizes["A"] * 28 * (owner_count - 1)
        weight_physical = raw_sizes["B"] * 28
        if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            weight_group_replication = raw_sizes["B"] * 4 * 6
    elif op_type == "MaxPool":
        layout = MaxPoolPhysicalLayout(profile_id)
        plan = layout.plan(
            input_shape=_shape(tensors[inputs[0]]),
            kernel_shape=tuple(attrs["kernel_shape"]),
            strides=tuple(attrs.get("strides", (1, 1))),
            pads=tuple(attrs.get("pads", (0, 0, 0, 0))),
            dilations=tuple(attrs.get("dilations", (1, 1))),
            ceil_mode=int(attrs.get("ceil_mode", 0)),
            storage_order=int(attrs.get("storage_order", 0)),
        )
        ports = {
            port: {
                **_feature_spec(tensors[inputs[0] if port == "A" else outputs[0]], profile_id),
                "physical_shape": tuple(plan["physical_shapes"][port]),
                "canonical_physical_shape": _canonical_physical_shape(
                    tuple(plan["physical_shapes"][port])
                ),
                "payload_bytes": int(plan["raw_sizes"][port]),
                "aligned_bytes": _align(int(plan["raw_sizes"][port])),
                "feature_tile": int(plan["channel_tile"]),
                "storage_sample_count": int(plan["storage_sample_count"]),
            }
            for port in ("A", "D")
        }
        raw_sizes = {port: int(value) for port, value in plan["raw_sizes"].items()}
        used_bytes = int(plan["per_slice_used_bytes"])
        capacity = int(plan["capacity_bytes"])
    elif op_type == "QLinearAdd":
        layout = QLinearAddPhysicalLayout(profile_id)
        plan = layout.plan(
            a_shape=_shape(tensors[inputs[0]]), b_shape=_shape(tensors[inputs[3]])
        )
        port_tensors = {
            "A": tensors[inputs[0]],
            "a_scale": tensors[inputs[1]],
            "a_zero_point": tensors[inputs[2]],
            "B": tensors[inputs[3]],
            "b_scale": tensors[inputs[4]],
            "b_zero_point": tensors[inputs[5]],
            "y_scale": tensors[inputs[6]],
            "y_zero_point": tensors[inputs[7]],
            "D": tensors[outputs[0]],
        }
        ports = {}
        for port, tensor in port_tensors.items():
            spec = (
                _feature_spec(tensor, profile_id)
                if port in {"A", "D"}
                or (port == "B" and len(_shape(tensor)) != 1)
                else _scalar_spec(tensor)
            )
            physical_shape = tuple(plan["physical_shapes"][port])
            ports[port] = {
                **spec,
                "physical_shape": physical_shape,
                "canonical_physical_shape": _canonical_physical_shape(physical_shape),
                "payload_bytes": int(plan["raw_sizes"][port]),
                "aligned_bytes": int(plan["aligned_sizes"][port]),
                "feature_tile": (
                    int(plan["feature_tile"]) if port in {"A", "B", "D"} else None
                ),
                "storage_sample_count": (
                    int(plan["storage_sample_count"])
                    if port in {"A", "D"}
                    or (port == "B" and len(_shape(tensor)) != 1)
                    else 0
                ),
            }
        raw_sizes = {port: int(value) for port, value in plan["raw_sizes"].items()}
        used_bytes = int(plan["per_slice_used_bytes"])
        capacity = int(plan["capacity_bytes"])
        if len(_shape(tensors[inputs[3]])) == 1 and profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            broadcast_group_replication = raw_sizes["B"] * 4 * 6
    elif op_type == "QLinearGlobalAveragePool":
        layout = GlobalAveragePoolPhysicalLayout(profile_id)
        output_rank = len(_shape(tensors[outputs[0]]))
        plan = layout.plan(
            input_shape=_shape(tensors[inputs[0]]),
            output_rank=output_rank,
            channels_last=int(attrs.get("channels_last", 0)),
        )
        port_tensors = {
            "A": tensors[inputs[0]],
            "x_scale": tensors[inputs[1]],
            "x_zero_point": tensors[inputs[2]],
            "y_scale": tensors[inputs[3]],
            "y_zero_point": tensors[inputs[4]],
            "D": tensors[outputs[0]],
        }
        ports = {}
        for port, tensor in port_tensors.items():
            spec = _feature_spec(tensor, profile_id) if port in {"A", "D"} else _scalar_spec(tensor)
            physical_shape = tuple(plan["physical_shapes"][port])
            ports[port] = {
                **spec,
                "physical_shape": physical_shape,
                "canonical_physical_shape": _canonical_physical_shape(physical_shape),
                "payload_bytes": int(plan["raw_sizes"][port]),
                "aligned_bytes": _align(int(plan["raw_sizes"][port])),
                "feature_tile": int(plan["channel_tile"]) if port in {"A", "D"} else None,
                "storage_sample_count": int(plan["storage_sample_count"]),
            }
        raw_sizes = {port: int(value) for port, value in plan["raw_sizes"].items()}
        used_bytes = int(plan["per_slice_used_bytes"])
        capacity = int(plan["capacity_bytes"])
        internal_int32 = raw_sizes["P"] * 28
    elif op_type == "QLinearMatMul":
        layout = QLinearMatMulPhysicalLayout(profile_id)
        plan = layout.plan(
            activation_shape=_shape(tensors[inputs[0]]),
            weight_shape=_shape(tensors[inputs[3]]),
            weight_dtype=tensors[inputs[3]]["dtype"],
        )
        port_tensors = {
            "A": tensors[inputs[0]],
            "a_scale": tensors[inputs[1]],
            "a_zero_point": tensors[inputs[2]],
            "B": tensors[inputs[3]],
            "b_scale": tensors[inputs[4]],
            "b_zero_point": tensors[inputs[5]],
            "y_scale": tensors[inputs[6]],
            "y_zero_point": tensors[inputs[7]],
            "D": tensors[outputs[0]],
        }
        ports = {}
        for port, tensor in port_tensors.items():
            spec = _feature_spec(tensor, profile_id) if port in {"A", "D"} else _scalar_spec(tensor)
            physical_shape = tuple(plan["physical_shapes"][port])
            ports[port] = {
                **spec,
                "physical_shape": physical_shape,
                "canonical_physical_shape": _canonical_physical_shape(physical_shape),
                "payload_bytes": int(plan["raw_sizes"][port]),
                "aligned_bytes": int(plan["aligned_sizes"][port]),
                "feature_tile": (
                    int(plan["k_tile"]) if port == "A" else int(plan["o_tile"])
                    if port == "D" else None
                ),
                "storage_sample_count": int(plan["storage_sample_count"]),
            }
        raw_sizes = {port: int(value) for port, value in plan["raw_sizes"].items()}
        used_bytes = int(plan["per_slice_used_bytes"])
        capacity = int(plan["capacity_bytes"])
        internal_int32 = raw_sizes["P"] * 28
        owner_count = 4 if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else 28
        ring_hop_bytes = raw_sizes["A"] * 28 * (owner_count - 1)
        weight_physical = raw_sizes["B"] * 28
        if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            weight_group_replication = raw_sizes["B"] * 4 * 6
    elif op_type in {"QuantizeLinear", "DequantizeLinear"}:
        port_tensors = {
            "A": tensors[inputs[0]],
            "scale": tensors[inputs[1]],
            "zero_point": tensors[inputs[2]],
            "D": tensors[outputs[0]],
        }
        ports = {
            port: (
                _feature_spec(tensor, profile_id)
                if port in {"A", "D"}
                else _scalar_spec(tensor)
            )
            for port, tensor in port_tensors.items()
        }
        raw_sizes = {port: int(spec["payload_bytes"]) for port, spec in ports.items()}
        used_bytes = sum(_align(value) for value in raw_sizes.values())
        capacity = TARGET_DRAM_GEOMETRY28.bytes_per_slice
    elif op_type == "Flatten":
        ports = {
            "A": _feature_spec(tensors[inputs[0]], profile_id),
            "D": _feature_spec(tensors[outputs[0]], profile_id),
        }
        raw_sizes = {}
        used_bytes = 0
        capacity = TARGET_DRAM_GEOMETRY28.bytes_per_slice
    else:
        raise ValueError(f"unsupported RTL28 network-audit op: {op_type}")

    logical_io = sum(_logical_bytes(tensors[tensor_id]) for tensor_id in inputs + outputs)
    qparam_physical = sum(
        value * 28
        for port, value in raw_sizes.items()
        if "scale" in port or "zero_point" in port or port == "multiplier"
    )
    output_spec = ports["D"]
    output_physical = int(output_spec["payload_bytes"]) * 28
    output_logical = _logical_bytes(tensors[outputs[0]])
    return {
        "node_id": node["node_id"],
        "graph_index": int(node["graph_index"]),
        "op_type": op_type,
        "profile_id": profile_id,
        "layout_id": _layout_id(op_type, profile_id),
        "ports": ports,
        "raw_sizes": raw_sizes,
        "per_slice_used_bytes": used_bytes,
        "capacity_bytes": capacity,
        "capacity_margin_bytes": capacity - used_bytes,
        "fits": used_bytes <= capacity,
        "logical_io_bytes": logical_io,
        "candidate_bundle_bytes_all_slices": used_bytes * 28,
        "internal_int32_bytes_all_slices": internal_int32,
        "qparam_physical_bytes_all_slices": qparam_physical,
        "weight_physical_bytes_all_slices": weight_physical,
        "weight_group_replication_bytes": weight_group_replication,
        "broadcast_group_replication_bytes": broadcast_group_replication,
        "static_ring_hop_bytes": ring_hop_bytes,
        "output_logical_bytes": output_logical,
        "output_physical_bytes_all_slices": output_physical,
        "output_lane_utilization": output_logical / output_physical,
    }


def _output_qparams(
    node: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    tensors: dict[str, dict[str, Any]],
) -> tuple[str, str] | None:
    inputs = node["input_tensor_ids"]
    if node["op_type"] == "QuantizeLinear":
        return inputs[1], inputs[2]
    if node["op_type"] in {"QLinearConv", "QLinearAdd", "QLinearMatMul"}:
        return inputs[6], inputs[7]
    if node["op_type"] == "QLinearGlobalAveragePool":
        return inputs[3], inputs[4]
    if node["op_type"] == "MaxPool":
        producer_id = tensors[inputs[0]]["producer_node_id"]
        if producer_id is None:
            return None
        return _output_qparams(nodes[producer_id], nodes, tensors)
    return None


def _input_qparams(
    node: dict[str, Any],
    tensor_id: str,
    nodes: dict[str, dict[str, Any]],
    tensors: dict[str, dict[str, Any]],
) -> tuple[str, str] | None:
    inputs = node["input_tensor_ids"]
    if node["op_type"] in {"QLinearConv", "QLinearMatMul"} and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    if node["op_type"] == "QLinearAdd":
        if tensor_id == inputs[0]:
            return inputs[1], inputs[2]
        if tensor_id == inputs[3]:
            return inputs[4], inputs[5]
    if node["op_type"] == "QLinearGlobalAveragePool" and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    if node["op_type"] == "DequantizeLinear" and tensor_id == inputs[0]:
        return inputs[1], inputs[2]
    if node["op_type"] == "MaxPool" and tensor_id == inputs[0]:
        producer_id = tensors[tensor_id]["producer_node_id"]
        return _output_qparams(nodes[producer_id], nodes, tensors) if producer_id else None
    return None


def _port_for(node: dict[str, Any], tensor_id: str, role: str) -> str:
    if role == "producer":
        return "D"
    op_type = node["op_type"]
    inputs = node["input_tensor_ids"]
    if op_type == "QLinearAdd" and tensor_id == inputs[3]:
        return "B"
    return "A"


def _tail_semantic(dtype: str, qparams: tuple[str, str] | None) -> str:
    if qparams is not None:
        return f"zero_point:{qparams[1]}"
    if np.dtype(dtype).kind == "f":
        return "float_zero"
    return "integer_zero"


def _signature(
    *,
    node: dict[str, Any],
    tensor: dict[str, Any],
    role: str,
    profile_id: str,
    plan: dict[str, Any],
    qparams: tuple[str, str] | None,
) -> dict[str, Any]:
    port = _port_for(node, tensor["tensor_id"], role)
    spec = plan["ports"][port]
    feature_tile = int(spec["feature_tile"])
    channels = _shape(tensor)[1]
    slice_regions: list[dict[str, Any]] = []
    if profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
        owner_order: Any = [list(item) for item in HIGH_RING_OWNERS]
        partition_policy = "seven_high_groups_sample_and_feature_partition"
        for group_id, owners in enumerate(HIGH_RING_OWNERS):
            sample_range = group_to_sample_range(group_id)
            for owner_step, slice_id in enumerate(owners):
                feature_start = owner_step * feature_tile
                feature_count = max(0, min(feature_tile, channels - feature_start))
                slice_regions.append(
                    {
                        "slice_id": slice_id,
                        "group_id": group_id,
                        "owner_step": owner_step,
                        "sample_start": sample_range.start,
                        "sample_count": sample_range.sample_count,
                        "storage_sample_count": max(GROUP_SAMPLE_COUNTS),
                        "feature_start": feature_start,
                        "feature_count": feature_count,
                        "active": feature_count > 0,
                    }
                )
    else:
        owner_order = list(LOW_RING_OWNERS)
        partition_policy = "global_low_ring_feature_partition"
        for owner_step, slice_id in enumerate(LOW_RING_OWNERS):
            feature_start = owner_step * feature_tile
            feature_count = max(0, min(feature_tile, channels - feature_start))
            slice_regions.append(
                {
                    "slice_id": slice_id,
                    "group_id": None,
                    "owner_step": owner_step,
                    "sample_start": 0,
                    "sample_count": BATCH_SIZE,
                    "storage_sample_count": BATCH_SIZE,
                    "feature_start": feature_start,
                    "feature_count": feature_count,
                    "active": feature_count > 0,
                }
            )
    slice_regions.sort(key=lambda item: item["slice_id"])
    return {
        "logical_shape": list(_shape(tensor)),
        "dtype": tensor["dtype"],
        "profile_id": profile_id,
        "partition_policy": partition_policy,
        "feature_tile": feature_tile,
        "storage_sample_count": int(spec["storage_sample_count"]),
        "raw_physical_shape": list(spec["physical_shape"]),
        "canonical_physical_shape": list(spec["canonical_physical_shape"]),
        "payload_bytes_per_slice": int(spec["payload_bytes"]),
        "aligned_bytes_per_slice": int(spec["aligned_bytes"]),
        "tail_semantic": _tail_semantic(tensor["dtype"], qparams),
        "byte_order": "little",
        "alignment_bytes": ALIGNMENT,
        "owner_order": owner_order,
        "slice_regions": slice_regions,
    }


def _signature_id(signature: dict[str, Any]) -> str:
    payload = json.dumps(
        signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sig-{hashlib.sha256(payload).hexdigest()[:16]}"


def _signature_differences(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    return [field for field in PHYSICAL_SIGNATURE_FIELDS if left[field] != right[field]]


def _scenario_profiles(
    catalog: dict[str, Any], scenario_id: str
) -> dict[str, str]:
    if scenario_id not in SCENARIO_IDS:
        raise ValueError(f"unknown RTL28 scenario {scenario_id!r}")
    matmul_nodes = [node for node in catalog["nodes"] if node["op_type"] == "QLinearMatMul"]
    if len(matmul_nodes) != 1:
        raise ValueError("formal graph must contain exactly one QLinearMatMul")
    matmul_index = int(matmul_nodes[0]["graph_index"])
    if scenario_id == GROUP_ONLY_SCENARIO:
        Profile28Schedule().validate()
        return {
            node["node_id"]: GROUP4X7_BATCH_CHANNEL28_PROFILE
            for node in catalog["nodes"]
        }
    Profile28Schedule(
        transitions=(
            ProfileTransition(
                source_profile=GROUP4X7_BATCH_CHANNEL28_PROFILE,
                target_profile=GLOBAL_RING28_PROFILE,
                boundary=TransitionBoundary.after_gap_before_matmul(),
            ),
        )
    ).validate()
    return {
        node["node_id"]: (
            GLOBAL_RING28_PROFILE
            if int(node["graph_index"]) >= matmul_index
            else GROUP4X7_BATCH_CHANNEL28_PROFILE
        )
        for node in catalog["nodes"]
    }


def _transition_audit(
    catalog: dict[str, Any],
    scenario_id: str,
    plans: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    profiles = _scenario_profiles(catalog, scenario_id)
    signatures: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    graph_input_signatures: dict[str, str] = {}
    for tensor_id in catalog["graph_input_ids"]:
        tensor = tensors[tensor_id]
        if tensor["producer_node_id"] is not None:
            raise ValueError(f"graph input {tensor_id!r} unexpectedly has a producer")
        if len(tensor["consumer_node_ids"]) != 1:
            raise ValueError(f"graph input {tensor_id!r} must have one consumer")
        consumer_id = tensor["consumer_node_ids"][0]
        consumer = nodes[consumer_id]
        consumer_profile = profiles[consumer_id]
        signature = _signature(
            node=consumer,
            tensor=tensor,
            role="consumer",
            profile_id=consumer_profile,
            plan=plans[(consumer_id, consumer_profile)],
            qparams=_input_qparams(consumer, tensor_id, nodes, tensors),
        )
        signature_id = _signature_id(signature)
        signatures[signature_id] = signature
        graph_input_signatures[tensor_id] = signature_id
    for tensor in catalog["tensors"]:
        producer_id = tensor["producer_node_id"]
        if producer_id is None:
            continue
        producer = nodes[producer_id]
        for consumer_id in tensor["consumer_node_ids"]:
            consumer = nodes[consumer_id]
            producer_profile = profiles[producer_id]
            consumer_profile = profiles[consumer_id]
            producer_qparams = _output_qparams(producer, nodes, tensors)
            consumer_qparams = _input_qparams(
                consumer, tensor["tensor_id"], nodes, tensors
            )
            producer_signature = _signature(
                node=producer,
                tensor=tensor,
                role="producer",
                profile_id=producer_profile,
                plan=plans[(producer_id, producer_profile)],
                qparams=producer_qparams,
            )
            consumer_signature = _signature(
                node=consumer,
                tensor=tensor,
                role="consumer",
                profile_id=consumer_profile,
                plan=plans[(consumer_id, consumer_profile)],
                qparams=consumer_qparams,
            )
            producer_signature_id = _signature_id(producer_signature)
            consumer_signature_id = _signature_id(consumer_signature)
            signatures[producer_signature_id] = producer_signature
            signatures[consumer_signature_id] = consumer_signature
            differences = _signature_differences(
                producer_signature, consumer_signature
            )
            profile_transition = producer_profile != consumer_profile
            physical_compatible = not differences
            if profile_transition:
                classification = "explicit_profile_relayout"
                alias_action = "materialize_destination_profile_buffer"
            elif producer["op_type"] == "Flatten" or consumer["op_type"] == "Flatten":
                classification = "zero_copy_view_chain"
                alias_action = "reuse_view_storage"
            elif consumer["op_type"] == "QLinearAdd":
                port = _port_for(consumer, tensor["tensor_id"], "consumer")
                classification = "byte_compatible_exact_alias_interface"
                alias_action = f"bind_add_{port}_to_producer_D"
            elif consumer["op_type"] == "QLinearMatMul":
                classification = "byte_compatible_exact_alias_interface"
                alias_action = "bind_matmul_A_to_producer_D"
            else:
                classification = "byte_compatible_rebase_required"
                alias_action = "reuse_runtime_tensor_after_address_binding"
            qparam_exact = (
                None
                if producer_qparams is None and consumer_qparams is None
                else producer_qparams == consumer_qparams
            )
            edges.append(
                {
                    "producer_node_id": producer_id,
                    "producer_op_type": producer["op_type"],
                    "producer_profile_id": producer_profile,
                    "producer_layout_id": _layout_id(
                        producer["op_type"], producer_profile
                    ),
                    "consumer_node_id": consumer_id,
                    "consumer_op_type": consumer["op_type"],
                    "consumer_profile_id": consumer_profile,
                    "consumer_layout_id": _layout_id(
                        consumer["op_type"], consumer_profile
                    ),
                    "tensor_id": tensor["tensor_id"],
                    "classification": classification,
                    "alias_action": alias_action,
                    "profile_transition": profile_transition,
                    "physical_signatures_equal": physical_compatible,
                    "signature_difference_fields": differences,
                    "policy_consistent": (
                        bool(differences) if profile_transition else not differences
                    ),
                    "qparam_identity_applicable": qparam_exact is not None,
                    "qparam_identity_exact": qparam_exact,
                    "producer_qparams": list(producer_qparams) if producer_qparams else None,
                    "consumer_qparams": list(consumer_qparams) if consumer_qparams else None,
                    "producer_signature_id": producer_signature_id,
                    "consumer_signature_id": consumer_signature_id,
                }
            )
    edges.sort(
        key=lambda item: (
            int(nodes[item["producer_node_id"]]["graph_index"]),
            int(nodes[item["consumer_node_id"]]["graph_index"]),
            item["tensor_id"],
        )
    )
    qparam_edges = [item for item in edges if item["qparam_identity_applicable"]]
    residual_checks: list[dict[str, Any]] = []
    edge_by_input = {
        (item["tensor_id"], item["consumer_node_id"]): item for item in edges
    }
    for node in catalog["nodes"]:
        if node["op_type"] != "QLinearAdd":
            continue
        left_id, right_id = node["input_tensor_ids"][0], node["input_tensor_ids"][3]
        if tensors[left_id]["producer_node_id"] is None or tensors[right_id]["producer_node_id"] is None:
            continue
        left = edge_by_input[(left_id, node["node_id"])]
        right = edge_by_input[(right_id, node["node_id"])]
        qparam_ids = (
            node["input_tensor_ids"][1],
            node["input_tensor_ids"][2],
            node["input_tensor_ids"][4],
            node["input_tensor_ids"][5],
            node["input_tensor_ids"][6],
            node["input_tensor_ids"][7],
        )
        residual_checks.append(
            {
                "node_id": node["node_id"],
                "left_tensor_id": left_id,
                "right_tensor_id": right_id,
                "distinct_branch_tensors": left_id != right_id,
                "same_consumer_profile": left["consumer_profile_id"]
                == right["consumer_profile_id"],
                "both_physical_signatures_equal": left["physical_signatures_equal"]
                and right["physical_signatures_equal"],
                "both_exact_alias_interfaces": left["classification"]
                == right["classification"]
                == "byte_compatible_exact_alias_interface",
                "six_qparam_tensor_ids_independent": len(set(qparam_ids)) == 6,
                "both_qparam_identities_exact": bool(left["qparam_identity_exact"])
                and bool(right["qparam_identity_exact"]),
            }
        )
    terminal_output_signatures: dict[str, str] = {}
    for tensor_id in catalog["graph_output_ids"]:
        tensor = tensors[tensor_id]
        producer_id = tensor["producer_node_id"]
        if producer_id is None:
            raise ValueError(f"graph output {tensor_id!r} has no producer")
        producer = nodes[producer_id]
        producer_profile = profiles[producer_id]
        signature = _signature(
            node=producer,
            tensor=tensor,
            role="producer",
            profile_id=producer_profile,
            plan=plans[(producer_id, producer_profile)],
            qparams=_output_qparams(producer, nodes, tensors),
        )
        signature_id = _signature_id(signature)
        signatures[signature_id] = signature
        terminal_output_signatures[tensor_id] = signature_id
    return {
        "scenario_id": scenario_id,
        "edge_count": len(edges),
        "classification_counts": dict(
            sorted(Counter(item["classification"] for item in edges).items())
        ),
        "profile_transition_edge_count": sum(
            item["profile_transition"] for item in edges
        ),
        "qparam_edge_count": len(qparam_edges),
        "all_qparam_identities_exact": all(
            item["qparam_identity_exact"] for item in qparam_edges
        ),
        "residual_add_count": len(residual_checks),
        "all_residual_adds_compatible": all(
            all(
                value
                for key, value in item.items()
                if key not in {"node_id", "left_tensor_id", "right_tensor_id"}
            )
            for item in residual_checks
        ),
        "all_edge_policies_verified": all(item["policy_consistent"] for item in edges),
        "signature_catalog": dict(sorted(signatures.items())),
        "graph_input_signatures": dict(sorted(graph_input_signatures.items())),
        "terminal_output_signatures": dict(sorted(terminal_output_signatures.items())),
        "residual_add_checks": residual_checks,
        "edges": edges,
    }


def _allocate_lifetimes(
    catalog: dict[str, Any],
    transition: dict[str, Any],
) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    signatures = transition["signature_catalog"]
    edges_by_tensor: dict[str, list[dict[str, Any]]] = {}
    for edge in transition["edges"]:
        edges_by_tensor.setdefault(edge["tensor_id"], []).append(edge)
    objects: list[dict[str, Any]] = []
    for tensor in catalog["tensors"]:
        tensor_id = tensor["tensor_id"]
        producer_id = tensor["producer_node_id"]
        consumers = tensor["consumer_node_ids"]
        if producer_id is None and tensor_id not in catalog["graph_input_ids"]:
            continue
        if producer_id is not None:
            start = int(nodes[producer_id]["graph_index"])
            related = edges_by_tensor.get(tensor_id, [])
            if related:
                signature_id = related[0]["producer_signature_id"]
            elif tensor_id in transition["terminal_output_signatures"]:
                signature_id = transition["terminal_output_signatures"][tensor_id]
            else:
                continue
        else:
            start = -1
            related = edges_by_tensor.get(tensor_id, [])
            if related:
                signature_id = related[0]["consumer_signature_id"]
            elif tensor_id in transition["graph_input_signatures"]:
                signature_id = transition["graph_input_signatures"][tensor_id]
            else:
                continue
        end = max(
            (int(nodes[item]["graph_index"]) for item in consumers),
            default=len(nodes),
        )
        objects.append(
            {
                "object_id": tensor_id,
                "kind": "runtime_tensor",
                "tensor_id": tensor_id,
                "start_step": start,
                "end_step": end,
                "size_bytes_per_slice": int(
                    signatures[signature_id]["aligned_bytes_per_slice"]
                ),
            }
        )
    for edge in transition["edges"]:
        if not edge["profile_transition"]:
            continue
        signature = signatures[edge["consumer_signature_id"]]
        step = int(nodes[edge["consumer_node_id"]]["graph_index"])
        objects.append(
            {
                "object_id": f"relayout:{edge['tensor_id']}:{edge['consumer_node_id']}",
                "kind": "transition_buffer",
                "tensor_id": edge["tensor_id"],
                "consumer_node_id": edge["consumer_node_id"],
                "start_step": step,
                "end_step": step,
                "size_bytes_per_slice": int(signature["aligned_bytes_per_slice"]),
            }
        )
    allocations: list[dict[str, Any]] = []
    high_water = 0
    reused_count = 0
    for item in sorted(
        objects,
        key=lambda value: (value["start_step"], value["kind"], value["object_id"]),
    ):
        occupied = sorted(
            (
                other["offset_bytes"],
                other["offset_bytes"] + other["size_bytes_per_slice"],
            )
            for other in allocations
            if other["end_step"] >= item["start_step"]
        )
        offset = 0
        for begin, end in occupied:
            offset = _align(offset)
            if offset + item["size_bytes_per_slice"] <= begin:
                break
            offset = max(offset, end)
        offset = _align(offset)
        if offset < high_water:
            reused_count += 1
        allocations.append({**item, "offset_bytes": offset})
        high_water = max(high_water, offset + item["size_bytes_per_slice"])
    conflicts: list[dict[str, str]] = []
    for index, left in enumerate(allocations):
        for right in allocations[index + 1 :]:
            lifetime_overlap = max(left["start_step"], right["start_step"]) <= min(
                left["end_step"], right["end_step"]
            )
            address_overlap = max(left["offset_bytes"], right["offset_bytes"]) < min(
                left["offset_bytes"] + left["size_bytes_per_slice"],
                right["offset_bytes"] + right["size_bytes_per_slice"],
            )
            if lifetime_overlap and address_overlap:
                conflicts.append({"left": left["object_id"], "right": right["object_id"]})
    by_id = {item["object_id"]: item for item in allocations}
    alias_checks: list[dict[str, Any]] = []
    for edge in transition["edges"]:
        transition_id = f"relayout:{edge['tensor_id']}:{edge['consumer_node_id']}"
        if edge["profile_transition"]:
            source = by_id[edge["tensor_id"]]
            target = by_id[transition_id]
            overlap = max(source["offset_bytes"], target["offset_bytes"]) < min(
                source["offset_bytes"] + source["size_bytes_per_slice"],
                target["offset_bytes"] + target["size_bytes_per_slice"],
            )
            conflict_free = not overlap
        else:
            conflict_free = transition_id not in by_id
        alias_checks.append(
            {
                "tensor_id": edge["tensor_id"],
                "consumer_node_id": edge["consumer_node_id"],
                "action": edge["alias_action"],
                "conflict_free": conflict_free,
            }
        )
    residual_ranges: list[dict[str, Any]] = []
    for check in transition["residual_add_checks"]:
        left = by_id[check["left_tensor_id"]]
        right = by_id[check["right_tensor_id"]]
        overlap = max(left["offset_bytes"], right["offset_bytes"]) < min(
            left["offset_bytes"] + left["size_bytes_per_slice"],
            right["offset_bytes"] + right["size_bytes_per_slice"],
        )
        residual_ranges.append(
            {
                **check,
                "left_offset": left["offset_bytes"],
                "right_offset": right["offset_bytes"],
                "address_ranges_disjoint": not overlap,
                "simultaneously_live_at_add": (
                    left["start_step"] <= int(nodes[check["node_id"]]["graph_index"]) <= left["end_step"]
                    and right["start_step"] <= int(nodes[check["node_id"]]["graph_index"]) <= right["end_step"]
                ),
            }
        )
    peak_live = 0
    for step in range(-1, len(nodes) + 1):
        peak_live = max(
            peak_live,
            sum(
                item["size_bytes_per_slice"]
                for item in allocations
                if item["start_step"] <= step <= item["end_step"]
            ),
        )
    capacity = TARGET_DRAM_GEOMETRY28.bytes_per_slice
    return {
        "allocation_policy": "deterministic_first_fit_16byte_aligned_per_slice_symmetric_candidate",
        "scope": "runtime activations and explicit profile-transition buffers; constants and operator-local scratch are costed separately",
        "runtime_tensor_count": sum(item["kind"] == "runtime_tensor" for item in allocations),
        "transition_buffer_count": sum(item["kind"] == "transition_buffer" for item in allocations),
        "reused_allocation_count": reused_count,
        "peak_live_bytes_per_slice": peak_live,
        "high_water_bytes_per_slice": high_water,
        "capacity_bytes_per_slice": capacity,
        "capacity_margin_bytes_per_slice": capacity - high_water,
        "all_allocations_fit": high_water <= capacity,
        "overlap_conflicts": conflicts,
        "all_lifetime_overlaps_address_disjoint": not conflicts,
        "alias_edge_checks": alias_checks,
        "all_alias_actions_conflict_free": all(item["conflict_free"] for item in alias_checks),
        "residual_branch_checks": residual_ranges,
        "all_residual_branches_distinct_live_and_disjoint": all(
            item["distinct_branch_tensors"]
            and item["simultaneously_live_at_add"]
            and item["address_ranges_disjoint"]
            for item in residual_ranges
        ),
        "allocations": allocations,
    }


def _view_checks(
    catalog: dict[str, Any],
    profiles: dict[str, str],
    plans: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    checks: list[dict[str, Any]] = []
    for node in catalog["nodes"]:
        if node["op_type"] != "Flatten":
            continue
        profile = profiles[node["node_id"]]
        plan = plans[(node["node_id"], profile)]
        left = plan["ports"]["A"]
        right = plan["ports"]["D"]
        input_shape = _shape(tensors[node["input_tensor_ids"][0]])
        output_shape = _shape(tensors[node["output_tensor_ids"][0]])
        checks.append(
            {
                "node_id": node["node_id"],
                "axis": int(node["attributes"].get("axis", 1)),
                "input_shape": list(input_shape),
                "output_shape": list(output_shape),
                "singleton_spatial_only": all(value == 1 for value in input_shape[2:]),
                "canonical_physical_shape_equal": left["canonical_physical_shape"]
                == right["canonical_physical_shape"],
                "payload_bytes_equal": left["payload_bytes"] == right["payload_bytes"],
                "dtype_equal": left["dtype"] == right["dtype"],
                "zero_copy": (
                    int(node["attributes"].get("axis", 1)) == 1
                    and all(value == 1 for value in input_shape[2:])
                    and left["canonical_physical_shape"] == right["canonical_physical_shape"]
                    and left["payload_bytes"] == right["payload_bytes"]
                    and left["dtype"] == right["dtype"]
                ),
            }
        )
    return checks


def _scenario_cost(
    catalog: dict[str, Any],
    scenario_id: str,
    profiles: dict[str, str],
    plans: dict[tuple[str, str], dict[str, Any]],
    transition: dict[str, Any],
) -> dict[str, Any]:
    node_costs = [plans[(node["node_id"], profiles[node["node_id"]])] for node in catalog["nodes"]]
    signatures = transition["signature_catalog"]
    relayout_bytes = sum(
        int(signatures[edge["producer_signature_id"]]["aligned_bytes_per_slice"]) * 28
        + int(signatures[edge["consumer_signature_id"]]["aligned_bytes_per_slice"]) * 28
        for edge in transition["edges"]
        if edge["profile_transition"]
    )
    max_node = max(node_costs, key=lambda item: item["per_slice_used_bytes"])
    profile_counts = Counter(item["profile_id"] for item in node_costs)
    return {
        "scenario_id": scenario_id,
        "cost_model": {
            "candidate_bundle_bytes_all_slices": "standalone operator region span times 28, including alignment and replicated ports",
            "static_ring_hop_bytes": "owner-local A payload times 28 owners times owner_count-1; topology byte-hop estimate, not measured traffic",
            "weight_group_replication_bytes": "extra Conv/MatMul weight bytes caused by copying the four-owner K/O set across six additional HIGH groups",
            "explicit_profile_relayout_read_write_bytes": "aligned source read plus aligned destination write for cross-profile runtime tensors",
            "output_lane_utilization": "logical output bytes divided by all 28 output payload bytes, including inactive sample/feature tail",
        },
        "node_count": len(node_costs),
        "profile_node_counts": dict(sorted(profile_counts.items())),
        "logical_io_bytes": sum(item["logical_io_bytes"] for item in node_costs),
        "candidate_bundle_bytes_all_slices": sum(item["candidate_bundle_bytes_all_slices"] for item in node_costs),
        "internal_int32_bytes_all_slices": sum(item["internal_int32_bytes_all_slices"] for item in node_costs),
        "qparam_physical_bytes_all_slices": sum(item["qparam_physical_bytes_all_slices"] for item in node_costs),
        "weight_physical_bytes_all_slices": sum(item["weight_physical_bytes_all_slices"] for item in node_costs),
        "weight_group_replication_bytes": sum(item["weight_group_replication_bytes"] for item in node_costs),
        "broadcast_group_replication_bytes": sum(item["broadcast_group_replication_bytes"] for item in node_costs),
        "static_ring_hop_bytes": sum(item["static_ring_hop_bytes"] for item in node_costs),
        "explicit_profile_relayout_read_write_bytes": relayout_bytes,
        "group_barrier_shape": {
            "sample_counts": list(GROUP_SAMPLE_COUNTS),
            "storage_slots_per_group": max(GROUP_SAMPLE_COUNTS),
            "three_sample_group_count": sum(value == 3 for value in GROUP_SAMPLE_COUNTS),
            "two_sample_group_count": sum(value == 2 for value in GROUP_SAMPLE_COUNTS),
            "inactive_storage_slots_per_barrier_wave": sum(
                max(GROUP_SAMPLE_COUNTS) - value for value in GROUP_SAMPLE_COUNTS
            ),
            "slot_utilization": BATCH_SIZE / (len(GROUP_SAMPLE_COUNTS) * max(GROUP_SAMPLE_COUNTS)),
        },
        "maximum_node_id": max_node["node_id"],
        "maximum_node_op_type": max_node["op_type"],
        "maximum_node_per_slice_used_bytes": max_node["per_slice_used_bytes"],
        "capacity_bytes_per_slice": TARGET_DRAM_GEOMETRY28.bytes_per_slice,
        "all_standalone_node_plans_fit": all(item["fits"] for item in node_costs),
        "minimum_output_lane_utilization": min(item["output_lane_utilization"] for item in node_costs),
        "node_costs": [
            {key: value for key, value in item.items() if key not in {"ports", "raw_sizes"}}
            for item in node_costs
        ],
    }


def audit_network28_candidates(catalog: dict[str, Any]) -> dict[str, Any]:
    if len(catalog.get("nodes", ())) != 78:
        raise ValueError("RTL28 network audit requires the frozen 78-node graph")
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    edge_count = sum(
        len(tensor["consumer_node_ids"])
        for tensor in catalog["tensors"]
        if tensor["producer_node_id"] is not None
    )
    if edge_count != 93:
        raise ValueError("RTL28 network audit requires the frozen 93 runtime edges")
    plans = {
        (node["node_id"], profile): _plan_node(node, tensors, profile)
        for node in catalog["nodes"]
        for profile in (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        )
    }
    scenarios: dict[str, Any] = {}
    for scenario_id in SCENARIO_IDS:
        profiles = _scenario_profiles(catalog, scenario_id)
        transition = _transition_audit(catalog, scenario_id, plans)
        memory = _allocate_lifetimes(catalog, transition)
        views = _view_checks(catalog, profiles, plans)
        cost = _scenario_cost(
            catalog, scenario_id, profiles, plans, transition
        )
        scenarios[scenario_id] = {
            "profile_assignment": profiles,
            "transition_audit": transition,
            "view_checks": views,
            "all_views_zero_copy": all(item["zero_copy"] for item in views),
            "memory_lifecycle": memory,
            "dry_run_cost": cost,
        }
    return {
        "schema_version": "0.1",
        "report_id": "w4_rtl28_network_candidate_audit_v1",
        "target_family": "rtl28",
        "slice_count": 28,
        "status": "candidate_software_evidence",
        "current_gate_eligible": True,
        "model_sha256": catalog["model_sha256"],
        "formal_node_count": 78,
        "formal_runtime_edge_count": 93,
        "scenarios": scenarios,
        "all_scenarios_pass": all(
            value["transition_audit"]["edge_count"] == 93
            and len(value["transition_audit"]["graph_input_signatures"]) == 1
            and len(value["transition_audit"]["terminal_output_signatures"]) == 1
            and value["transition_audit"]["profile_transition_edge_count"]
            == (1 if scenario_id == GLOBAL_HEAD_SCENARIO else 0)
            and value["transition_audit"]["qparam_edge_count"] == 91
            and value["transition_audit"]["all_qparam_identities_exact"]
            and value["transition_audit"]["residual_add_count"] == 16
            and value["transition_audit"]["all_residual_adds_compatible"]
            and value["transition_audit"]["all_edge_policies_verified"]
            and value["all_views_zero_copy"]
            and value["memory_lifecycle"]["runtime_tensor_count"] == 79
            and len(value["memory_lifecycle"]["alias_edge_checks"]) == 93
            and len(value["memory_lifecycle"]["residual_branch_checks"]) == 16
            and value["memory_lifecycle"]["all_allocations_fit"]
            and value["memory_lifecycle"]["all_lifetime_overlaps_address_disjoint"]
            and value["memory_lifecycle"]["all_alias_actions_conflict_free"]
            and value["memory_lifecycle"]["all_residual_branches_distinct_live_and_disjoint"]
            and value["dry_run_cost"]["node_count"] == 78
            and value["dry_run_cost"]["all_standalone_node_plans_fit"]
            for scenario_id, value in scenarios.items()
        ),
        "hardware_approval": False,
        "g4_passed": False,
        "w5_authorized": False,
        "non_claims": [
            "No W3 tensor payload was read or regenerated.",
            "Static byte-hop and utilization values are not target cycle, bandwidth, energy, or performance measurements.",
            "Candidate first-fit offsets are not approved board DDR addresses or a W5 execution plan.",
            "No JSON, bitstream, target simulator, RTL, or hardware execution was produced.",
        ],
    }


def edge_evidence(report: dict[str, Any]) -> dict[str, Any]:
    scenarios = {
        scenario_id: {
            "transition_audit": value["transition_audit"],
            "view_checks": value["view_checks"],
            "all_views_zero_copy": value["all_views_zero_copy"],
            "memory_lifecycle": value["memory_lifecycle"],
        }
        for scenario_id, value in report["scenarios"].items()
    }
    return {
        "schema_version": "0.1",
        "report_id": "w4_rtl28_network_physical_edge_audit_v1",
        "evidence_kind": "network_physical_edge_audit",
        "target_family": "rtl28",
        "slice_count": 28,
        "status": "candidate_software_evidence",
        "current_gate_eligible": True,
        "model_sha256": report["model_sha256"],
        "edge_count": 93,
        "qparam_edge_count": 91,
        "residual_add_count": 16,
        "all_scenarios_pass": report["all_scenarios_pass"],
        "hardware_approval": False,
        "g4_passed": False,
        "w5_authorized": False,
        "non_claims": report["non_claims"],
        "scenarios": scenarios,
    }


def cost_evidence(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "report_id": "w4_rtl28_network_profile_cost_v1",
        "evidence_kind": "network_profile_cost",
        "target_family": "rtl28",
        "slice_count": 28,
        "status": "candidate_software_evidence",
        "current_gate_eligible": True,
        "model_sha256": report["model_sha256"],
        "scenario_count": len(report["scenarios"]),
        "all_scenarios_pass": report["all_scenarios_pass"],
        "hardware_approval": False,
        "g4_passed": False,
        "w5_authorized": False,
        "non_claims": report["non_claims"],
        "scenarios": {
            scenario_id: value["dry_run_cost"]
            for scenario_id, value in report["scenarios"].items()
        },
    }


__all__ = [
    "GLOBAL_HEAD_SCENARIO",
    "GROUP_ONLY_SCENARIO",
    "SCENARIO_IDS",
    "audit_network28_candidates",
    "cost_evidence",
    "edge_evidence",
]
