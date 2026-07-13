"""Legacy16 network dry-run implementation; diagnostic evidence only.

Its 93-edge catalog, lifetime algorithm and report structure may inform the
future RTL28 C3 rewrite.  Its physical signatures, profiles, capacities and
ring formulas are superseded by ADR-007 and cannot satisfy the current G4.
"""

from __future__ import annotations


TARGET_FAMILY = "legacy16"
CURRENT_GATE_ELIGIBLE = False

import math
from collections import Counter
from typing import Any

import numpy as np

from .add16_layout import QLinearAddBatch16PhysicalLayout, QLinearAddChannel16PhysicalLayout
from .avgpool16_layout import (
    GlobalAveragePoolBatch16PhysicalLayout,
    GlobalAveragePoolChannel16PhysicalLayout,
)
from .conv16_layout import ConvBatch16PhysicalLayout
from .conv16_ring_layout import ConvRing16PhysicalLayout
from .matmul16_layout import QLinearMatMulBatch16PhysicalLayout, QLinearMatMulRing16PhysicalLayout
from .maxpool16_layout import MaxPoolBatch16PhysicalLayout, MaxPoolChannel16PhysicalLayout
from .memory import LEGACY_DRAM_GEOMETRY16
from .w4_profiles import PROFILE_POLICIES


ALIGNMENT = 16
PROFILE_NAMES = ("batch", "ring_channel")


def _align(value: int, alignment: int = ALIGNMENT) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _shape(tensor: dict[str, Any], batch_size: int = 16) -> tuple[int, ...]:
    result: list[int] = []
    for index, value in enumerate(tensor["shape"]):
        if isinstance(value, int):
            result.append(value)
        elif index == 0:
            result.append(batch_size)
        else:
            raise ValueError(f"unsupported symbolic tensor shape: {tensor['shape']}")
    if any(value <= 0 for value in result):
        raise ValueError(f"tensor dimensions must be positive: {tensor['shape']}")
    return tuple(result)


def _logical_bytes(tensor: dict[str, Any]) -> int:
    return int(np.prod(_shape(tensor), dtype=np.int64)) * np.dtype(tensor["dtype"]).itemsize


def _canonical_axes(
    axes: tuple[int, ...], extents: tuple[int, ...], logical_shape: tuple[int, ...]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    kept = [
        index
        for index, axis in enumerate(axes)
        if logical_shape[axis] != 1 or extents[index] != 1
    ]
    return (
        tuple(axes[index] for index in kept),
        tuple(extents[index] for index in kept),
    )


def _simple_signature(tensor: dict[str, Any]) -> dict[str, Any]:
    shape = _shape(tensor)
    axes = tuple(range(1, len(shape)))
    extents = shape[1:]
    axes, extents = _canonical_axes(axes, extents, shape)
    return _signature_record(
        tensor,
        partition={"kind": "batch", "axis": 0, "tile": 1},
        axes=axes,
        extents=extents,
        feature_capacity=shape[1] if len(shape) > 1 else 1,
        tail_semantic="none",
    )


def _feature_signature(
    tensor: dict[str, Any], profile: str, zero_point_id: str | None
) -> dict[str, Any]:
    shape = _shape(tensor)
    if len(shape) not in {2, 4}:
        raise ValueError(f"feature layout requires rank-2/rank-4, got {shape}")
    features = shape[1]
    if profile == "batch":
        feature_capacity = _align(features, 8)
        if len(shape) == 4:
            axes = (2, 3, 1)
            extents = (shape[2], shape[3], feature_capacity)
        else:
            axes = (1,)
            extents = (feature_capacity,)
        partition = {"kind": "batch", "axis": 0, "tile": 1}
    else:
        feature_tile = math.ceil(features / 16)
        feature_capacity = feature_tile * 16
        if len(shape) == 4:
            axes = (0, 2, 3, 1)
            extents = (shape[0], shape[2], shape[3], feature_tile)
        else:
            axes = (0, 1)
            extents = (shape[0], feature_tile)
        partition = {"kind": "feature", "axis": 1, "tile": feature_tile}
    axes, extents = _canonical_axes(axes, extents, shape)
    tail = (
        "none"
        if feature_capacity == features
        else f"zero_point:{zero_point_id or 'unresolved'}"
    )
    return _signature_record(
        tensor,
        partition=partition,
        axes=axes,
        extents=extents,
        feature_capacity=feature_capacity,
        tail_semantic=tail,
    )


def _signature_record(
    tensor: dict[str, Any],
    *,
    partition: dict[str, Any],
    axes: tuple[int, ...],
    extents: tuple[int, ...],
    feature_capacity: int,
    tail_semantic: str,
) -> dict[str, Any]:
    itemsize = np.dtype(tensor["dtype"]).itemsize
    return {
        "logical_shape": list(_shape(tensor)),
        "dtype": tensor["dtype"],
        "itemsize": itemsize,
        "partition": partition,
        "physical_axis_order": list(axes),
        "per_slice_physical_shape": list(extents),
        "per_slice_payload_bytes": int(np.prod(extents, dtype=np.int64)) * itemsize,
        "feature_capacity": feature_capacity,
        "tail_semantic": tail_semantic,
        "byte_order": "little",
        "alignment_bytes": ALIGNMENT,
    }


def _output_qparams(
    node: dict[str, Any], nodes: dict[str, dict[str, Any]], tensors: dict[str, dict[str, Any]]
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


def _input_qparams(node: dict[str, Any], tensor_id: str) -> tuple[str, str] | None:
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
    return None


def _node_tensor_signature(
    node: dict[str, Any],
    tensor: dict[str, Any],
    *,
    role: str,
    profile: str,
    nodes: dict[str, dict[str, Any]],
    tensors: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    op_type = node["op_type"]
    tensor_id = tensor["tensor_id"]
    if op_type in {"QuantizeLinear", "DequantizeLinear", "Flatten"}:
        return _simple_signature(tensor)
    if role == "producer":
        qparams = _output_qparams(node, nodes, tensors)
    elif op_type == "MaxPool":
        producer_id = tensors[node["input_tensor_ids"][0]]["producer_node_id"]
        qparams = _output_qparams(nodes[producer_id], nodes, tensors) if producer_id else None
    else:
        qparams = _input_qparams(node, tensor_id)
    zero_point_id = qparams[1] if qparams else None
    if op_type in {
        "QLinearConv",
        "MaxPool",
        "QLinearAdd",
        "QLinearGlobalAveragePool",
        "QLinearMatMul",
    }:
        return _feature_signature(tensor, profile, zero_point_id)
    raise ValueError(f"unsupported W4 runtime layout signature for {op_type}")


def _signature_differences(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    return sorted(key for key in left if left[key] != right[key])


def _transition_audit(catalog: dict[str, Any], profile: str) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    edges: list[dict[str, Any]] = []
    for tensor in catalog["tensors"]:
        producer_id = tensor["producer_node_id"]
        if producer_id is None:
            continue
        producer = nodes[producer_id]
        for consumer_id in tensor["consumer_node_ids"]:
            consumer = nodes[consumer_id]
            pair = (producer["op_type"], consumer["op_type"])
            expected = PROFILE_POLICIES[profile][pair]
            producer_signature = _node_tensor_signature(
                producer,
                tensor,
                role="producer",
                profile=profile,
                nodes=nodes,
                tensors=tensors,
            )
            consumer_signature = _node_tensor_signature(
                consumer,
                tensor,
                role="consumer",
                profile=profile,
                nodes=nodes,
                tensors=tensors,
            )
            differences = _signature_differences(producer_signature, consumer_signature)
            physical_equal = not differences
            policy_consistent = (
                physical_equal
                if expected != "explicit_relayout"
                else not physical_equal
            )
            producer_qparams = _output_qparams(producer, nodes, tensors)
            consumer_qparams = _input_qparams(consumer, tensor["tensor_id"])
            if consumer["op_type"] == "MaxPool":
                consumer_qparams = producer_qparams
            qparam_exact = (
                None
                if producer_qparams is None or consumer_qparams is None
                else producer_qparams == consumer_qparams
            )
            edges.append(
                {
                    "producer_node_id": producer_id,
                    "producer_op_type": producer["op_type"],
                    "consumer_node_id": consumer_id,
                    "consumer_op_type": consumer["op_type"],
                    "tensor_id": tensor["tensor_id"],
                    "expected_transition": expected,
                    "physical_signatures_equal": physical_equal,
                    "signature_difference_fields": differences,
                    "policy_consistent": policy_consistent,
                    "qparam_identity_exact": qparam_exact,
                    "producer_signature": producer_signature,
                    "consumer_signature": consumer_signature,
                }
            )
    edges.sort(key=lambda item: (nodes[item["producer_node_id"]]["graph_index"], nodes[item["consumer_node_id"]]["graph_index"], item["tensor_id"]))
    return {
        "edge_count": len(edges),
        "classification_counts": dict(sorted(Counter(item["expected_transition"] for item in edges).items())),
        "physically_equal_edge_count": sum(item["physical_signatures_equal"] for item in edges),
        "explicit_relayout_edge_count": sum(item["expected_transition"] == "explicit_relayout" for item in edges),
        "all_policy_relations_physically_verified": all(item["policy_consistent"] for item in edges),
        "all_quantized_qparams_exact": all(item["qparam_identity_exact"] for item in edges if item["qparam_identity_exact"] is not None),
        "edges": edges,
    }


def _plan_node(
    node: dict[str, Any], tensors: dict[str, dict[str, Any]], profile: str
) -> dict[str, Any]:
    inputs = node["input_tensor_ids"]
    outputs = node["output_tensor_ids"]
    attrs = node["attributes"]
    op_type = node["op_type"]
    if op_type == "QLinearConv":
        layout = ConvBatch16PhysicalLayout() if profile == "batch" else ConvRing16PhysicalLayout()
        plan = layout.plan(
            activation_shape=_shape(tensors[inputs[0]]),
            weight_shape=_shape(tensors[inputs[3]]),
            strides=tuple(attrs.get("strides", (1, 1))),
            pads=tuple(attrs.get("pads", (0, 0, 0, 0))),
            dilations=tuple(attrs.get("dilations", (1, 1))),
            group=int(attrs.get("group", 1)),
        )
    elif op_type == "MaxPool":
        layout = MaxPoolBatch16PhysicalLayout() if profile == "batch" else MaxPoolChannel16PhysicalLayout()
        plan = layout.plan(
            input_shape=_shape(tensors[inputs[0]]),
            kernel_shape=tuple(attrs["kernel_shape"]),
            strides=tuple(attrs.get("strides", (1, 1))),
            pads=tuple(attrs.get("pads", (0, 0, 0, 0))),
            dilations=tuple(attrs.get("dilations", (1, 1))),
            ceil_mode=int(attrs.get("ceil_mode", 0)),
            storage_order=int(attrs.get("storage_order", 0)),
        )
    elif op_type == "QLinearAdd":
        layout = QLinearAddBatch16PhysicalLayout() if profile == "batch" else QLinearAddChannel16PhysicalLayout()
        plan = layout.plan(a_shape=_shape(tensors[inputs[0]]), b_shape=_shape(tensors[inputs[3]]))
    elif op_type == "QLinearGlobalAveragePool":
        layout = GlobalAveragePoolBatch16PhysicalLayout() if profile == "batch" else GlobalAveragePoolChannel16PhysicalLayout()
        plan = layout.plan(input_shape=_shape(tensors[inputs[0]]), channels_last=int(attrs.get("channels_last", 0)))
    elif op_type == "QLinearMatMul":
        layout = QLinearMatMulBatch16PhysicalLayout() if profile == "batch" else QLinearMatMulRing16PhysicalLayout()
        plan = layout.plan(activation_shape=_shape(tensors[inputs[0]]), weight_shape=_shape(tensors[inputs[3]]))
    elif op_type in {"QuantizeLinear", "DequantizeLinear"}:
        raw_sizes = {
            "A": _logical_bytes(tensors[inputs[0]]) // 16,
            "scale": 4,
            "zero_point": 1,
            "D": _logical_bytes(tensors[outputs[0]]) // 16,
        }
        cursor = sum(_align(value) for value in raw_sizes.values())
        plan = {
            "raw_sizes": raw_sizes,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": LEGACY_DRAM_GEOMETRY16.bytes_per_slice,
        }
    elif op_type == "Flatten":
        plan = {
            "raw_sizes": {},
            "per_slice_used_bytes": 0,
            "capacity_bytes": LEGACY_DRAM_GEOMETRY16.bytes_per_slice,
        }
    else:
        raise ValueError(f"unsupported W4 dry-run op: {op_type}")
    logical_io_bytes = sum(_logical_bytes(tensors[item]) for item in inputs + outputs)
    raw_sizes = plan.get("raw_sizes", {})
    ring_transfer = 0
    if profile == "ring_channel" and op_type in {"QLinearConv", "QLinearMatMul"}:
        ring_transfer = int(raw_sizes["A"]) * 16 * 15
    return {
        "node_id": node["node_id"],
        "graph_index": node["graph_index"],
        "op_type": op_type,
        "logical_io_bytes": logical_io_bytes,
        "candidate_bundle_bytes_all_slices": int(plan["per_slice_used_bytes"]) * 16,
        "per_slice_used_bytes": int(plan["per_slice_used_bytes"]),
        "per_slice_capacity_bytes": int(plan["capacity_bytes"]),
        "per_slice_capacity_margin_bytes": int(plan["capacity_bytes"] - plan["per_slice_used_bytes"]),
        "internal_int32_bytes_all_slices": int(raw_sizes.get("P", 0)) * 16,
        "estimated_ring_neighbor_bytes": ring_transfer,
    }


def _allocate_lifetimes(
    catalog: dict[str, Any], profile: str, transition: dict[str, Any]
) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    objects: list[dict[str, Any]] = []
    for tensor in catalog["tensors"]:
        producer_id = tensor["producer_node_id"]
        consumers = tensor["consumer_node_ids"]
        if producer_id is None and tensor["tensor_id"] not in catalog["graph_input_ids"]:
            continue
        if producer_id is not None:
            producer = nodes[producer_id]
            signature = _node_tensor_signature(producer, tensor, role="producer", profile=profile, nodes=nodes, tensors=tensors)
            start = producer["graph_index"]
        else:
            consumer = nodes[consumers[0]]
            signature = _node_tensor_signature(consumer, tensor, role="consumer", profile=profile, nodes=nodes, tensors=tensors)
            start = -1
        end = max((nodes[item]["graph_index"] for item in consumers), default=len(nodes))
        objects.append({
            "object_id": tensor["tensor_id"],
            "kind": "runtime_tensor",
            "tensor_id": tensor["tensor_id"],
            "start_step": start,
            "end_step": end,
            "size_bytes_per_slice": _align(signature["per_slice_payload_bytes"]),
        })
    for edge in transition["edges"]:
        if edge["expected_transition"] != "explicit_relayout":
            continue
        signature = edge["consumer_signature"]
        step = nodes[edge["consumer_node_id"]]["graph_index"]
        objects.append({
            "object_id": f"relayout:{edge['tensor_id']}:{edge['consumer_node_id']}",
            "kind": "transition_buffer",
            "tensor_id": edge["tensor_id"],
            "consumer_node_id": edge["consumer_node_id"],
            "start_step": step,
            "end_step": step,
            "size_bytes_per_slice": _align(signature["per_slice_payload_bytes"]),
        })
    allocations: list[dict[str, Any]] = []
    high_water = 0
    reused_allocation_count = 0
    for item in sorted(objects, key=lambda value: (value["start_step"], value["kind"], value["object_id"])):
        occupied = sorted(
            (other["offset_bytes"], other["offset_bytes"] + other["size_bytes_per_slice"])
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
            reused_allocation_count += 1
        allocation = {**item, "offset_bytes": offset}
        allocations.append(allocation)
        high_water = max(high_water, offset + item["size_bytes_per_slice"])
    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(allocations):
        for right in allocations[index + 1 :]:
            lifetime_overlap = max(left["start_step"], right["start_step"]) <= min(left["end_step"], right["end_step"])
            address_overlap = max(left["offset_bytes"], right["offset_bytes"]) < min(
                left["offset_bytes"] + left["size_bytes_per_slice"],
                right["offset_bytes"] + right["size_bytes_per_slice"],
            )
            if lifetime_overlap and address_overlap:
                conflicts.append({"left": left["object_id"], "right": right["object_id"]})
    by_id = {item["object_id"]: item for item in allocations}
    alias_checks: list[dict[str, Any]] = []
    for edge in transition["edges"]:
        source = by_id[edge["tensor_id"]]
        transition_id = f"relayout:{edge['tensor_id']}:{edge['consumer_node_id']}"
        if edge["physical_signatures_equal"]:
            alias_checks.append(
                {
                    "tensor_id": edge["tensor_id"],
                    "consumer_node_id": edge["consumer_node_id"],
                    "action": "reuse_runtime_tensor_storage",
                    "source_object_id": source["object_id"],
                    "transition_object_id": None,
                    "conflict_free": transition_id not in by_id,
                }
            )
        else:
            target = by_id[transition_id]
            source_range = (
                source["offset_bytes"],
                source["offset_bytes"] + source["size_bytes_per_slice"],
            )
            target_range = (
                target["offset_bytes"],
                target["offset_bytes"] + target["size_bytes_per_slice"],
            )
            overlap = max(source_range[0], target_range[0]) < min(
                source_range[1], target_range[1]
            )
            alias_checks.append(
                {
                    "tensor_id": edge["tensor_id"],
                    "consumer_node_id": edge["consumer_node_id"],
                    "action": "materialize_explicit_relayout",
                    "source_object_id": source["object_id"],
                    "transition_object_id": target["object_id"],
                    "conflict_free": not overlap,
                }
            )
    residual_checks: list[dict[str, Any]] = []
    for node in catalog["nodes"]:
        if node["op_type"] != "QLinearAdd":
            continue
        left_id, right_id = node["input_tensor_ids"][0], node["input_tensor_ids"][3]
        if left_id not in by_id or right_id not in by_id:
            continue
        left, right = by_id[left_id], by_id[right_id]
        overlap = max(left["offset_bytes"], right["offset_bytes"]) < min(
            left["offset_bytes"] + left["size_bytes_per_slice"],
            right["offset_bytes"] + right["size_bytes_per_slice"],
        )
        residual_checks.append({
            "node_id": node["node_id"],
            "left_tensor_id": left_id,
            "right_tensor_id": right_id,
            "distinct_tensors": left_id != right_id,
            "address_ranges_disjoint": not overlap,
        })
    peak_live = 0
    for step in range(-1, len(nodes) + 1):
        live = sum(item["size_bytes_per_slice"] for item in allocations if item["start_step"] <= step <= item["end_step"])
        peak_live = max(peak_live, live)
    capacity = LEGACY_DRAM_GEOMETRY16.bytes_per_slice
    return {
        "allocation_policy": "deterministic first-fit, 16-byte aligned, per-slice symmetric candidate offsets",
        "scope": "runtime activations plus explicit transition buffers; constants and operator-local scratch are reported separately",
        "object_count": len(allocations),
        "runtime_tensor_count": sum(item["kind"] == "runtime_tensor" for item in allocations),
        "transition_buffer_count": sum(item["kind"] == "transition_buffer" for item in allocations),
        "reused_allocation_count": reused_allocation_count,
        "peak_live_bytes_per_slice": peak_live,
        "high_water_bytes_per_slice": high_water,
        "capacity_bytes_per_slice": capacity,
        "capacity_margin_bytes_per_slice": capacity - high_water,
        "all_allocations_fit": high_water <= capacity,
        "overlap_conflicts": conflicts,
        "all_lifetime_overlaps_address_disjoint": not conflicts,
        "alias_edge_checks": alias_checks,
        "all_alias_actions_conflict_free": all(
            item["conflict_free"] for item in alias_checks
        ),
        "residual_branch_checks": residual_checks,
        "all_residual_branches_distinct_and_disjoint": all(
            item["distinct_tensors"] and item["address_ranges_disjoint"]
            for item in residual_checks
        ),
        "allocations": allocations,
    }


def audit_network_candidates(catalog: dict[str, Any]) -> dict[str, Any]:
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    profiles: dict[str, Any] = {}
    for profile in PROFILE_NAMES:
        transition = _transition_audit(catalog, profile)
        node_costs = [_plan_node(node, tensors, profile) for node in catalog["nodes"]]
        relayout_bytes = sum(
            edge["producer_signature"]["per_slice_payload_bytes"] * 16
            + edge["consumer_signature"]["per_slice_payload_bytes"] * 16
            for edge in transition["edges"]
            if edge["expected_transition"] == "explicit_relayout"
        )
        lifetimes = _allocate_lifetimes(catalog, profile, transition)
        profiles[profile] = {
            "transition_audit": transition,
            "dry_run_cost": {
                "cost_model": {
                    "logical_io_bytes": "sum of formal tensor bytes read/written by every node; repeated consumers are counted repeatedly",
                    "candidate_bundle_bytes_all_slices": "sum of each standalone candidate plan span across 16 slices, including alignment, replicated constants and local P/D regions",
                    "explicit_relayout_read_write_bytes": "source physical payload read plus destination physical payload write for every explicit transition",
                    "estimated_ring_neighbor_bytes": "A-tile payload times 16 owners times 15 hops for each ring Conv/MatMul; topology estimate, not measured traffic",
                },
                "node_count": len(node_costs),
                "logical_io_bytes": sum(item["logical_io_bytes"] for item in node_costs),
                "candidate_bundle_bytes_all_slices": sum(item["candidate_bundle_bytes_all_slices"] for item in node_costs),
                "internal_int32_bytes_all_slices": sum(item["internal_int32_bytes_all_slices"] for item in node_costs),
                "estimated_ring_neighbor_bytes": sum(item["estimated_ring_neighbor_bytes"] for item in node_costs),
                "explicit_relayout_read_write_bytes": relayout_bytes,
                "maximum_node_per_slice_used_bytes": max(item["per_slice_used_bytes"] for item in node_costs),
                "all_standalone_node_plans_fit": all(item["per_slice_capacity_margin_bytes"] >= 0 for item in node_costs),
                "node_costs": node_costs,
            },
            "memory_lifecycle": lifetimes,
        }
    return {
        "schema_version": "0.1",
        "report_id": "w4_network_candidate_dry_run_v1",
        "model_sha256": catalog["model_sha256"],
        "status": "candidate_software_evidence",
        "scope": "93-edge physical compatibility, profile dry-run cost, and candidate activation lifetime allocation",
        "non_claims": [
            "This report is not target hardware timing or energy measurement.",
            "Synthetic offsets are not approved DDR addresses or a W5 execution plan.",
            "No JSON, bitstream, simulator execution or hardware execution is generated.",
        ],
        "profiles": profiles,
        "all_profiles_pass": all(
            value["transition_audit"]["all_policy_relations_physically_verified"]
            and value["transition_audit"]["all_quantized_qparams_exact"]
            and value["dry_run_cost"]["all_standalone_node_plans_fit"]
            and value["memory_lifecycle"]["all_allocations_fit"]
            and value["memory_lifecycle"]["all_lifetime_overlaps_address_disjoint"]
            and value["memory_lifecycle"]["all_alias_actions_conflict_free"]
            and value["memory_lifecycle"]["all_residual_branches_distinct_and_disjoint"]
            for value in profiles.values()
        ),
    }
