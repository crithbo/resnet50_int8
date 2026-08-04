from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_config_system import validate_stage_config_system
from .w5_conv_preflight import _load_npy


SCHEMA = "resnet50-stage-state-lifetime-contract-v1"
CONTRACT_PATH = (
    "contracts/operator_config/stage_state_lifetime_contract_v1.json"
)
LOWERING_PATH = "contracts/resnet50_r5_lowering_bundle.json"
SYSTEM_PATH = "contracts/operator_config/stage_config_system_v1.json"
RUNTIME_MANIFEST = "artifacts/w3/golden_batch16/manifest.json"
MINIMAL_TWO_STAGE_PATH = (
    "contracts/operator_config/minimal_two_stage_lifecycle_v1.json"
)
VIEW_REQUEST_ID = "r5:hwop-0073-00"
SA_FAMILIES = {"ConvInt32Accumulate", "MatMulInt32Accumulate"}


class StageStateLifetimeContractError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StageStateLifetimeContractError(
            f"cannot load state/lifetime input {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise StageStateLifetimeContractError(
            f"state/lifetime JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise StageStateLifetimeContractError(
            f"required state/lifetime input is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _required_modules(hw_op_type: str) -> list[str]:
    if hw_op_type in SA_FAMILIES:
        return ["IGA", "LSU", "SA"]
    if hw_op_type == "View":
        return []
    return ["IGA", "LSU", "GA"]


def _tensor_edges(requests: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    producer_by_tensor: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for request in requests:
        for output in request.get("ports", {}).get("outputs", []):
            if not isinstance(output, Mapping):
                continue
            tensor_id = output.get("tensor_id")
            if not isinstance(tensor_id, str):
                continue
            if tensor_id in producer_by_tensor:
                raise StageStateLifetimeContractError(
                    f"multiple producers for tensor: {tensor_id}"
                )
            producer_by_tensor[tensor_id] = (request, dict(output))

    edges: list[dict[str, Any]] = []
    external_inputs: list[dict[str, Any]] = []
    for consumer in requests:
        for port_index, raw_input in enumerate(
            consumer.get("ports", {}).get("inputs", [])
        ):
            if not isinstance(raw_input, Mapping):
                continue
            input_port = dict(raw_input)
            if input_port.get("kind") == "initializer":
                continue
            tensor_id = input_port.get("tensor_id")
            produced = producer_by_tensor.get(str(tensor_id))
            if produced is None:
                external_inputs.append(
                    {
                        "consumer_request_id": consumer["request_id"],
                        "consumer_port_index": port_index,
                        "tensor_id": tensor_id,
                        "kind": input_port.get("kind"),
                        "dtype": input_port.get("dtype"),
                        "shape": input_port.get("shape"),
                    }
                )
                continue
            producer, output_port = produced
            if (
                output_port.get("dtype") != input_port.get("dtype")
                or output_port.get("shape") != input_port.get("shape")
                or output_port.get("identity_sha256")
                != input_port.get("identity_sha256")
            ):
                raise StageStateLifetimeContractError(
                    "typed producer/consumer identity differs for "
                    f"{tensor_id}: {producer['request_id']} -> "
                    f"{consumer['request_id']}"
                )
            producer_type = producer["identity"]["hw_op_type"]
            consumer_type = consumer["identity"]["hw_op_type"]
            is_view_edge = "View" in (producer_type, consumer_type)
            is_intra_node = (
                producer["identity"]["node_id"]
                == consumer["identity"]["node_id"]
            )
            edges.append(
                {
                    "edge_id": (
                        f"{producer['request_id']}->{consumer['request_id']}"
                        f":{tensor_id}"
                    ),
                    "producer_request_id": producer["request_id"],
                    "consumer_request_id": consumer["request_id"],
                    "tensor_id": tensor_id,
                    "dtype": input_port["dtype"],
                    "shape": input_port["shape"],
                    "byte_count": int(
                        np.prod(input_port["shape"], dtype=np.int64)
                    )
                    * {
                        "uint8": 1,
                        "int8": 1,
                        "float16": 2,
                        "int32": 4,
                        "float32": 4,
                    }[str(input_port["dtype"])],
                    "typed_identity_exact": True,
                    "edge_kind": (
                        "view_adjacent"
                        if is_view_edge
                        else (
                            "intra_node_lowering"
                            if is_intra_node
                            else "inter_node"
                        )
                    ),
                    "logical_alias_eligible": is_view_edge,
                    "physical_allocation_status": (
                        "blocked_until_address_offset_and_lifetime_are_bound"
                    ),
                    "implicit_register_or_buffer_reuse_allowed": False,
                }
            )
    return edges, external_inputs


def _view_proof(
    root: Path, requests: list[dict[str, Any]], edges: list[dict]
) -> dict[str, Any]:
    matches = [
        request
        for request in requests
        if request["request_id"] == VIEW_REQUEST_ID
    ]
    if len(matches) != 1:
        raise StageStateLifetimeContractError("exact View request is missing")
    request = matches[0]
    inputs = request["ports"]["inputs"]
    outputs = request["ports"]["outputs"]
    if len(inputs) != 1 or len(outputs) != 1:
        raise StageStateLifetimeContractError("View port arity differs")
    input_port = inputs[0]
    output_port = outputs[0]
    manifest = _load(root / RUNTIME_MANIFEST)
    input_tensor = _load_npy(
        root / "artifacts/w3/golden_batch16",
        manifest,
        manifest["tensors"][input_port["tensor_id"]],
    )
    output_tensor = _load_npy(
        root / "artifacts/w3/golden_batch16",
        manifest,
        manifest["tensors"][output_port["tensor_id"]],
    )
    input_bytes = np.ascontiguousarray(input_tensor).tobytes()
    output_bytes = np.ascontiguousarray(output_tensor).tobytes()
    if (
        input_tensor.shape != (16, 2048, 1, 1)
        or output_tensor.shape != (16, 2048)
        or input_tensor.dtype != np.dtype("float32")
        or output_tensor.dtype != np.dtype("float32")
        or not input_tensor.flags.c_contiguous
        or not output_tensor.flags.c_contiguous
        or input_bytes != output_bytes
        or not np.array_equal(input_tensor.reshape(16, 2048), output_tensor)
    ):
        raise StageStateLifetimeContractError(
            "View logical element-order/byte proof differs"
        )
    adjacent = [
        edge for edge in edges if edge["edge_kind"] == "view_adjacent"
    ]
    if len(adjacent) != 2:
        raise StageStateLifetimeContractError(
            "View must have one producer and one consumer edge"
        )
    byte_sha = sha256_bytes(input_bytes)
    return {
        "request_id": VIEW_REQUEST_ID,
        "axis": 1,
        "input_shape": [16, 2048, 1, 1],
        "output_shape": [16, 2048],
        "dtype": "float32",
        "element_count": 32768,
        "byte_count": len(input_bytes),
        "input_contiguous_c_order": True,
        "output_contiguous_c_order": True,
        "flattened_element_order_equal": True,
        "exact_byte_equal": True,
        "input_bytes_sha256": byte_sha,
        "output_bytes_sha256": byte_sha,
        "logical_zero_copy_proven": True,
        "physical_zero_copy_proven": False,
        "physical_blockers": [
            "B_VIEW_PRODUCER_ALLOCATION",
            "B_VIEW_CONSUMER_ALLOCATION",
            "B_VIEW_BYTE_OFFSET_IDENTITY",
            "B_VIEW_BUFFER_LIFETIME",
        ],
        "disposition": (
            "logical alias only; do not emit JSON and do not release until "
            "producer/output and consumer/input physical allocation, offset, "
            "layout and lifetime are identical"
        ),
        "adjacent_edges": [edge["edge_id"] for edge in adjacent],
    }


def build_stage_state_lifetime_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    lowering = _load(root / LOWERING_PATH)
    system = _load(root / SYSTEM_PATH)
    validate_r5_lowering_bundle(lowering, root)
    validate_stage_config_system(system, root)
    requests = [
        dict(item)
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping)
    ]
    plans = [
        dict(item)
        for item in system.get("stage_plans", [])
        if isinstance(item, Mapping)
    ]
    if (
        len(requests) != 133
        or len(plans) != 133
        or [item["ordinal"] for item in requests] != list(range(133))
        or [item["request_id"] for item in requests]
        != [item["request_id"] for item in plans]
    ):
        raise StageStateLifetimeContractError(
            "ordered 133-stage identity differs"
        )
    edges, external_inputs = _tensor_edges(requests)
    view = _view_proof(root, requests, edges)
    minimal_two_stage = _load(root / MINIMAL_TWO_STAGE_PATH)
    minimal_self_hash = minimal_two_stage.get("contract_sha256")
    minimal_payload = dict(minimal_two_stage)
    minimal_payload.pop("contract_sha256", None)
    if (
        minimal_two_stage.get("status")
        != "local_e2_complete_dynamic_hardware_pending"
        or minimal_two_stage.get("candidate_release") is not False
        or minimal_two_stage.get("formal_target_config") is not False
        or minimal_two_stage.get("server_package") is not False
        or minimal_self_hash
        != sha256_bytes(canonical_json_bytes(minimal_payload))
        or minimal_two_stage.get("probe", {}).get("stage0")
        != "prefill_mul_fp32MN_fp32M_fp32MN"
        or minimal_two_stage.get("probe", {}).get("stage1")
        != "prefill_add_fp32MN_fp32MN_fp32MN"
        or minimal_two_stage.get("probe", {}).get("shape") != [1, 8, 32]
        or len(minimal_two_stage.get("closed_local_semantics", [])) != 6
    ):
        raise StageStateLifetimeContractError(
            "minimal two-stage lifecycle contract differs"
        )
    minimal_artifact = minimal_two_stage.get("artifact")
    if not isinstance(minimal_artifact, Mapping):
        raise StageStateLifetimeContractError(
            "minimal two-stage lifecycle artifact binding is missing"
        )
    minimal_artifact_root = root / str(minimal_artifact.get("path", ""))
    if (
        not minimal_artifact_root.is_dir()
        or sha256_file(minimal_artifact_root / "manifest.json")
        != minimal_artifact.get("manifest_sha256")
        or sha256_file(minimal_artifact_root / "local_e2_report.json")
        != minimal_artifact.get("report_sha256")
    ):
        raise StageStateLifetimeContractError(
            "minimal two-stage lifecycle artifact identity differs"
        )
    minimal_report = _load(minimal_artifact_root / "local_e2_report.json")
    runtime_lifecycle = minimal_report.get("transport_and_state", {}).get(
        "runtime_lifecycle", {}
    )
    if (
        minimal_report.get("status")
        != "MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE"
        or runtime_lifecycle.get("validated") is not True
        or runtime_lifecycle.get("stage_count") != 2
        or runtime_lifecycle.get("repeat_num") != 2
        or runtime_lifecycle.get("start_comp_count") != 2
        or runtime_lifecycle.get("completion_barrier_count") != 2
        or runtime_lifecycle.get("dependency", {}).get(
            "consumer_external_preload"
        )
        is not False
        or minimal_report.get("numeric_execution", {}).get(
            "stage0_golden_bit_exact"
        )
        is not True
        or minimal_report.get("numeric_execution", {}).get(
            "stage1_golden_bit_exact"
        )
        is not True
    ):
        raise StageStateLifetimeContractError(
            "minimal two-stage lifecycle local E2 evidence differs"
        )

    ordered_states: list[dict[str, Any]] = []
    sa_stage_ids: list[str] = []
    for request, plan in zip(requests, plans, strict=True):
        hw_type = request["identity"]["hw_op_type"]
        is_view = hw_type == "View"
        if is_view:
            transition = "logical_alias_no_hardware_config"
            blockers = view["physical_blockers"]
        else:
            transition = "blocked_before_config_encoding"
            blockers = list(plan["candidate_blockers"])
        if hw_type in SA_FAMILIES:
            sa_stage_ids.append(request["request_id"])
            if "B_SA_INT8_CSA_NUMERIC" not in blockers:
                raise StageStateLifetimeContractError(
                    f"SA numeric blocker missing: {request['request_id']}"
                )
        ordered_states.append(
            {
                "ordinal": request["ordinal"],
                "request_id": request["request_id"],
                "hw_op_type": hw_type,
                "required_config_modules": _required_modules(hw_type),
                "config_transition": transition,
                "config_update_sequence_available": False,
                "implicit_prior_state_allowed": False,
                "buffer_allocation_available": False,
                "address_alias_or_copy_decision_available": (
                    view["logical_zero_copy_proven"] if is_view else False
                ),
                "lifetime_release_available": False,
                "blockers": blockers,
            }
        )

    family_counts = Counter(
        request["identity"]["hw_op_type"] for request in requests
    )
    if (
        len(sa_stage_ids) != 54
        or family_counts["ConvInt32Accumulate"] != 53
        or family_counts["MatMulInt32Accumulate"] != 1
    ):
        raise StageStateLifetimeContractError(
            "SA stage inventory differs"
        )
    conv_signature_groups: dict[str, dict[str, Any]] = {}
    for request in requests:
        if request["identity"]["hw_op_type"] != "ConvInt32Accumulate":
            continue
        geometry = request["logical_geometry"]
        signature = sha256_bytes(canonical_json_bytes(geometry))
        group = conv_signature_groups.setdefault(
            signature,
            {
                "signature_sha256": signature,
                "logical_geometry": geometry,
                "stage_ids": [],
            },
        )
        group["stage_ids"].append(request["request_id"])
    conv_signatures = []
    for signature in sorted(conv_signature_groups):
        group = conv_signature_groups[signature]
        conv_signatures.append(
            {
                **group,
                "stage_count": len(group["stage_ids"]),
                "exact_int8_authorized_template_available": False,
                "control_json_emission_allowed": False,
                "blockers": [
                    "B_SA_INT8_CSA_NUMERIC",
                    "B_CONV_FULL_SCHEDULE",
                    "B_CONV_STAGE_CONFIG_LIFETIME",
                ],
            }
        )
    if (
        len(conv_signatures) != 20
        or sum(item["stage_count"] for item in conv_signatures) != 53
    ):
        raise StageStateLifetimeContractError(
            "Conv SA shape-signature inventory differs"
        )
    matmul_request = next(
        request
        for request in requests
        if request["identity"]["hw_op_type"] == "MatMulInt32Accumulate"
    )
    matmul_mnk = matmul_request["logical_geometry"]["mnk"]
    if matmul_mnk != {"M": 16, "N": 1000, "K": 2048}:
        raise StageStateLifetimeContractError(
            "MatMul logical MNK signature differs"
        )

    n2n_typed = [
        request
        for request in requests
        if "N2N" in request["identity"]["hw_op_type"].upper()
        or "NEIGHBOR" in request["identity"]["hw_op_type"].upper()
    ]
    n2n_blocked = [
        plan
        for plan in plans
        if any("N2N" in blocker for blocker in plan["candidate_blockers"])
    ]
    if n2n_typed or n2n_blocked:
        raise StageStateLifetimeContractError(
            "current typed plan unexpectedly selects N2N"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "ordered_dag_logical_view_and_minimal_two_stage_lifecycle_closed_"
            "full_network_physical_state_blocked"
        ),
        "inputs": {
            "lowering_bundle": _binding(root, LOWERING_PATH),
            "stage_config_system": _binding(root, SYSTEM_PATH),
            "runtime_manifest": _binding(root, RUNTIME_MANIFEST),
            "minimal_two_stage_lifecycle": _binding(
                root, MINIMAL_TWO_STAGE_PATH
            ),
        },
        "ordered_config_plan": {
            "stage_count": len(ordered_states),
            "encoded_config_transition_count": 0,
            "blocked_compute_stage_count": sum(
                item["config_transition"]
                == "blocked_before_config_encoding"
                for item in ordered_states
            ),
            "logical_alias_stage_count": sum(
                item["config_transition"]
                == "logical_alias_no_hardware_config"
                for item in ordered_states
            ),
            "implicit_prior_state_allowed": False,
            "stages": ordered_states,
        },
        "typed_tensor_dag": {
            "edge_count": len(edges),
            "external_noninitializer_input_count": len(external_inputs),
            "typed_identity_mismatch_count": 0,
            "physical_allocation_bound_edge_count": 0,
            "implicit_reuse_edge_count": 0,
            "edge_kind_counts": dict(
                sorted(Counter(edge["edge_kind"] for edge in edges).items())
            ),
            "edges": edges,
            "external_inputs": external_inputs,
        },
        "view": view,
        "minimal_two_stage_lifecycle": {
            "status": "local_e2_complete_dynamic_hardware_pending",
            "synthetic_probe_only": True,
            "stage_count": 2,
            "runtime_sequence": runtime_lifecycle["runtime_sequence"],
            "producer_consumer_alias": runtime_lifecycle["dependency"],
            "config_reload": runtime_lifecycle["config_reload"],
            "repeat_num": runtime_lifecycle["repeat_num"],
            "start_comp_count": runtime_lifecycle["start_comp_count"],
            "completion_barrier_count": runtime_lifecycle[
                "completion_barrier_count"
            ],
            "final_barrier_command_index": runtime_lifecycle[
                "final_barrier_command_index"
            ],
            "dual_golden_bit_exact": True,
            "producer_backed_input_preloaded": False,
            "candidate_release": False,
            "formal_target_config": False,
            "full_network_projection_allowed": False,
            "remaining_boundary": (
                "the generic two-stage transport/lifetime invariant is closed "
                "at local E2, but every real 133-stage edge still requires its "
                "family config, allocation, offset, lifetime and E4/E5 evidence"
            ),
        },
        "sa_control_boundary": {
            "stage_count": len(sa_stage_ids),
            "conv_stage_count": 53,
            "matmul_stage_count": 1,
            "conv_shape_signature_count": len(conv_signatures),
            "conv_shape_signatures": conv_signatures,
            "matmul_logical_signature": {
                "request_id": matmul_request["request_id"],
                "request_sha256": matmul_request["request_sha256"],
                "mnk": matmul_mnk,
                "input_shapes": matmul_request["logical_geometry"][
                    "input_shapes"
                ],
                "output_shapes": matmul_request["logical_geometry"][
                    "output_shapes"
                ],
                "exact_int8_authorized_template_available": False,
                "physical_tile_and_tail_schedule_proven": False,
                "blockers": [
                    "B_SA_INT8_CSA_NUMERIC",
                    "B_MATMUL_TAIL",
                    "B_MATMUL_PSUM",
                ],
            },
            "all_carry_B_SA_INT8_CSA_NUMERIC": True,
            "control_schedule_may_progress_independently": True,
            "numeric_release_allowed": False,
            "stage_ids": sa_stage_ids,
            "remaining_control_work": (
                "all 20 Conv logical shape signatures and the exact MatMul "
                "M16xN1000xK2048 signature are inventoried; no authorized "
                "INT8 SA template supplies their physical tile, loop, wave, "
                "tail or buffer-lifetime equations, so CONFIG encoding remains "
                "fail-closed rather than inferred from ONNX geometry"
            ),
        },
        "n2n": {
            "typed_n2n_stage_count": 0,
            "stage_plan_n2n_blocker_count": 0,
            "selected_n2n_config_count": 0,
            "required_for_gap": False,
            "current_critical_path": False,
            "rule": (
                "do not emit N2N unless a future physical schedule proves a "
                "cross-slice material transfer; logical reduction shape or "
                "operator name alone is insufficient"
            ),
            "future_gate": [
                "physical neighbor pair",
                "hard-wired ping-pong sequence",
                "mem_loop_minus_one transfer count",
                "configure-clear boundary",
            ],
        },
        "release": {
            "ordered_plan_complete": False,
            "reason": (
                "the request/DAG order and all typed tensor identities are "
                "closed, and a synthetic two-stage producer/consumer lifecycle "
                "now proves config reload, alias, barrier, termination and dual "
                "golden handling at local E2. Candidate target configs remain "
                "0/133, so CONFIG "
                "update/reuse/disable words, physical addresses, buffer owners "
                "and lifetimes cannot yet be assigned without fabrication"
            ),
            "next_machine_gate": (
                "each newly released family emitter must replace its stage's "
                "blocked transition with explicit module update/reuse/disable "
                "and bind every incident edge to allocation, offset and lifetime"
            ),
        },
    }
    payload["contract_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_stage_state_lifetime_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_stage_state_lifetime_contract(project_root)
    if value != expected:
        raise StageStateLifetimeContractError(
            "stage state/lifetime contract differs from hash-bound inputs"
        )


def write_stage_state_lifetime_contract(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONTRACT_PATH",
    "SCHEMA",
    "StageStateLifetimeContractError",
    "build_stage_state_lifetime_contract",
    "validate_stage_state_lifetime_contract",
    "write_stage_state_lifetime_contract",
]
