from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


class QLinearAddPredesignError(ValueError):
    pass


_QPARAM_ROLES = (
    "a_scale",
    "a_zero_point",
    "b_scale",
    "b_zero_point",
    "y_scale",
    "y_zero_point",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QLinearAddPredesignError(f"{path}: expected an object")
    return value


def _qlinearadd_records(typed_contract: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for hw_op in typed_contract.get("hw_ops", []):
        if hw_op.get("onnx_op_type") != "QLinearAdd":
            continue
        parameters = {
            item["name"]: item
            for item in hw_op.get("parameters", [])
            if item.get("name") in _QPARAM_ROLES
        }
        if tuple(parameters) != _QPARAM_ROLES:
            raise QLinearAddPredesignError(
                f"{hw_op.get('hw_op_id')}: six qparams are missing or reordered"
            )
        broadcast = hw_op["logical_geometry"]["broadcast"]
        ports = hw_op["ports"]
        record: dict[str, Any] = {
            "node_id": hw_op["node_id"],
            "hw_op_id": hw_op["hw_op_id"],
            "class": (
                "broadcast_bias_add"
                if hw_op["node_id"] == "node-0076"
                else "same_shape_residual_add"
            ),
            "a_shape": broadcast["a_shape"],
            "b_shape": broadcast["b_shape"],
            "y_shape": broadcast["output_shape"],
            "tensors": {
                "a": ports["inputs"][0]["tensor_id"],
                "b": ports["inputs"][3]["tensor_id"],
                "y": ports["outputs"][0]["tensor_id"],
            },
            "qparams": {},
        }
        for role in _QPARAM_ROLES:
            value = parameters[role]["value"]
            descriptor = {
                "value": value["scalar"],
                "value_sha256": value["value_sha256"],
            }
            if "float32_bits" in value:
                descriptor["float32_bits"] = value["float32_bits"]
            record["qparams"][role] = descriptor
        records.append(record)
    return records


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _qparam_values(hw_op: dict[str, Any]) -> dict[str, int | float]:
    return {
        item["name"]: item["value"]["scalar"]
        for item in hw_op["parameters"]
        if item["name"] in _QPARAM_ROLES
    }


def _affine_reassociation_counterexamples(
    typed_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    counterexamples: list[dict[str, Any]] = []
    values = np.arange(256, dtype=np.int32)
    for hw_op in typed_contract["hw_ops"]:
        if hw_op.get("onnx_op_type") != "QLinearAdd":
            continue
        qparam = _qparam_values(hw_op)
        branch: dict[str, np.ndarray] = {}
        for name in ("a", "b"):
            scale = np.float32(qparam[f"{name}_scale"])
            zero = int(qparam[f"{name}_zero_point"])
            branch[f"{name}_w3"] = (values - zero).astype(np.float32) * scale
            offset = np.float32(-np.float32(zero) * scale)
            branch[f"{name}_affine"] = values.astype(np.float32) * scale + offset
        w3_sum = np.float32(
            branch["a_w3"][:, None] + branch["b_w3"][None, :]
        )
        affine_sum = np.float32(
            branch["a_affine"][:, None] + branch["b_affine"][None, :]
        )
        y_scale = np.float32(qparam["y_scale"])
        y_zero = int(qparam["y_zero_point"])
        w3 = np.clip(
            np.rint(np.float32(w3_sum / y_scale)).astype(np.int64) + y_zero,
            0,
            255,
        ).astype(np.uint8)
        affine = np.clip(
            np.rint(np.float32(affine_sum / y_scale)).astype(np.int64) + y_zero,
            0,
            255,
        ).astype(np.uint8)
        mismatches = np.argwhere(w3 != affine)
        if mismatches.size:
            a, b = (int(item) for item in mismatches[0])
            counterexamples.append(
                {
                    "node_id": hw_op["node_id"],
                    "mismatch_pair_count": int(len(mismatches)),
                    "first": {
                        "a": a,
                        "b": b,
                        "w3": int(w3[a, b]),
                        "affine_reassociated": int(affine[a, b]),
                    },
                }
            )
    return counterexamples


def validate_qlinearadd_predesign(
    contract_path: Path,
    *,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    root = (repository_root or contract_path.parents[2]).resolve()
    contract = _load(contract_path.resolve())
    errors: list[str] = []
    warnings: list[str] = []

    if contract.get("status") != "PREDESIGN_COMPLETE_MATERIALIZATION_FORBIDDEN":
        errors.append("status is not fail-closed predesign")
    if contract.get("candidate_release") is not False:
        errors.append("candidate_release must be false")
    if contract.get("formal_target_instance_allowed") is not False:
        errors.append("formal_target_instance_allowed must be false")

    for relative, expected in contract.get("provenance", {}).items():
        source = root / relative
        if not source.is_file():
            errors.append(f"missing provenance source: {relative}")
        elif _sha256(source) != expected:
            errors.append(f"provenance SHA mismatch: {relative}")
    for relative, receipt in contract.get("mutable_read_receipt", {}).items():
        source = root / relative
        if not source.is_file():
            warnings.append(f"mutable read receipt source missing: {relative}")
        elif _sha256(source) != receipt.get("sha256"):
            warnings.append(f"mutable read receipt drift: {relative}")
    for dependency in contract.get("current_match_rule_dependencies", []):
        relative = dependency.get("path")
        source = root / str(relative)
        if not source.is_file():
            errors.append(f"current-match rule missing: {relative}")
            continue
        if _sha256(source) != dependency.get("sha256"):
            errors.append(f"current-match rule SHA mismatch: {relative}")
            continue
        text = source.read_text(encoding="utf-8")
        for rule_id in dependency.get("required_rule_ids", []):
            if rule_id not in text:
                errors.append(
                    f"current-match rule ID missing: {relative}: {rule_id}"
                )

    typed_path = root / "contracts/typed_config_parameter_contract.json"
    lifetime_path = (
        root / "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    )
    typed = _load(typed_path)
    lifetime = _load(lifetime_path)
    records = _qlinearadd_records(typed)
    coverage = contract.get("coverage", {})
    if len(records) != coverage.get("instance_count"):
        errors.append("QLinearAdd instance count mismatch")
    if sum(item["class"] == "same_shape_residual_add" for item in records) != 16:
        errors.append("same-shape residual coverage is not 16")
    if sum(item["class"] == "broadcast_bias_add" for item in records) != 1:
        errors.append("broadcast-bias coverage is not 1")
    if _canonical_sha256(records) != coverage.get("instance_manifest_sha256"):
        errors.append("17-instance typed/qparam manifest hash mismatch")
    expected_instances = [
        f"{item['node_id']}/{item['hw_op_id']}" for item in records
    ]
    if coverage.get("instances") != expected_instances:
        errors.append("ordered instance identity list mismatch")
    actual_shape_classes: dict[
        tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]], int
    ] = {}
    for item in records:
        key = (
            tuple(item["a_shape"]),
            tuple(item["b_shape"]),
            tuple(item["y_shape"]),
        )
        actual_shape_classes[key] = actual_shape_classes.get(key, 0) + 1
    expected_shape_classes = {
        (
            tuple(item["a"]),
            tuple(item["b"]),
            tuple(item["y"]),
        ): item["count"]
        for item in coverage.get("shape_classes", [])
    }
    if actual_shape_classes != expected_shape_classes:
        errors.append("five QLinearAdd shape classes mismatch")

    broadcast = [item for item in records if item["class"] == "broadcast_bias_add"]
    if len(broadcast) != 1 or (
        broadcast[0]["a_shape"],
        broadcast[0]["b_shape"],
        broadcast[0]["y_shape"],
    ) != ([16, 1000], [1000], [16, 1000]):
        errors.append("node0076 broadcast geometry mismatch")
    elif broadcast[0]["qparams"]["y_zero_point"]["value"] != 60:
        errors.append("node0076 nonzero output zero-point holdout mismatch")

    roles = contract.get("six_qparam_transport", {}).get(
        "required_roles_in_order"
    )
    if roles != list(_QPARAM_ROLES):
        errors.append("six-qparam transport order mismatch")

    expected_counterexamples = contract.get("front_half_reuse", {}).get(
        "affine_reassociation_exhaustive_counterexamples", {}
    ).get("final_uint8_difference")
    actual_counterexamples = _affine_reassociation_counterexamples(typed)
    if actual_counterexamples != expected_counterexamples:
        errors.append("affine reassociation counterexample set mismatch")

    qlinearadd_requests = {
        f"r5:{item['hw_op_id']}" for item in records
    }
    related_edges = [
        edge
        for edge in lifetime["typed_tensor_dag"]["edges"]
        if edge.get("producer_request_id") in qlinearadd_requests
        or edge.get("consumer_request_id") in qlinearadd_requests
    ]
    if not related_edges:
        errors.append("no QLinearAdd lifetime edges found")
    for edge in related_edges:
        if (
            edge.get("physical_allocation_status")
            != "blocked_until_address_offset_and_lifetime_are_bound"
        ):
            errors.append(f"unexpected materialized edge: {edge.get('edge_id')}")
    stage_records = [
        item
        for item in lifetime.get("ordered_config_plan", {}).get("stages", [])
        if item.get("request_id") in qlinearadd_requests
    ]
    if len(stage_records) != 17:
        errors.append("QLinearAdd lifetime stage count is not 17")
    for item in stage_records:
        for field in (
            "buffer_allocation_available",
            "lifetime_release_available",
            "address_alias_or_copy_decision_available",
        ):
            if item.get(field) is not False:
                errors.append(
                    f"{item.get('request_id')}: {field} unexpectedly available"
                )

    add_oracle = _load(
        root / "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
    )
    streams = add_oracle.get("stream_engine", {})
    if (
        streams.get("stream0", {}).get("target") != "A"
        or streams.get("stream1", {}).get("target") != "B"
        or streams.get("stream2", {}).get("target") != "D"
        or streams.get("stream2", {}).get("mode") != "write"
    ):
        errors.append("native add oracle does not expose A/B/D stream structure")
    ga = add_oracle.get("general_array", {})
    if not ga.get("inport", {}).get("inport0", {}).get("uint8tofp32") == "true":
        errors.append("native add oracle A ingress is not uint8-to-fp32")
    if not ga.get("inport", {}).get("inport1", {}).get("uint8tofp32") == "true":
        errors.append("native add oracle B ingress is not uint8-to-fp32")

    forbidden = contract.get("forbidden_outputs", {})
    if not forbidden or any(value is not False for value in forbidden.values()):
        errors.append("every materialized/server output must remain false")
    dependency = contract.get("dependency_on_quant_tail", {})
    if dependency.get("dependency_id") != "R5_GAP_EXACT_UINT8_QUANT_TAIL":
        errors.append("P0-A dependency ID mismatch")
    if dependency.get("materialization_must_remain_blocked") is not True:
        errors.append("P0-A dependency does not block materialization")
    p0a_receipt = dependency.get("p0a_receipt", {})
    p0a_path = root / str(p0a_receipt.get("path", ""))
    if not p0a_path.is_file():
        errors.append("P0-A dependency contract is missing")
    else:
        p0a = _load(p0a_path)
        if _sha256(p0a_path) != p0a_receipt.get("sha256"):
            errors.append("P0-A dependency SHA mismatch")
        if p0a.get("status") != p0a_receipt.get("status"):
            errors.append("P0-A dependency status mismatch")
        decision = p0a.get("pure_configuration_decision", {})
        if decision.get("decision") != p0a_receipt.get("decision"):
            errors.append("P0-A pure-configuration decision mismatch")
        ce = next(
            (
                item
                for item in p0a.get("counterexamples", [])
                if item.get("id") == "CE_FMA_VS_SEQUENTIAL_ROUND"
            ),
            None,
        )
        expected_ce = dependency.get("p0a_first_common_unknown", {})
        if ce is None:
            errors.append("P0-A GA MAC rounding counterexample is missing")
        elif (
            ce["inputs"].get("int32") != expected_ce.get("int32")
            or ce["inputs"].get("multiplier_bits")
            != expected_ce.get("multiplier_bits")
            or ce["inputs"].get("zero_point")
            != expected_ce.get("zero_point")
            or ce.get("expected_sequential_uint8")
            != expected_ce.get("required_sequential_uint8")
            or ce.get("one_round_fused_model_uint8")
            != expected_ce.get("one_round_fused_uint8")
        ):
            errors.append("P0-A GA MAC rounding counterexample mismatch")
    impact = dependency.get("qlinearadd_impact", {})
    if impact.get("single_stage_fused") != "REMAINS_UNDECIDABLE":
        errors.append("single-stage decision was upgraded without proof")
    if (
        impact.get("two_stage_explicit_scratch")
        != "REMAINS_STRUCTURALLY_FEASIBLE_NUMERIC_TAIL_UNCLOSED"
    ):
        errors.append("two-stage numeric tail was upgraded without proof")
    if impact.get("materialization") != "FORBIDDEN":
        errors.append("P0-A impact does not forbid materialization")

    report = {
        "schema": "qlinearadd_composite_backend_predesign_validation_v1",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "coverage": {
            "instances": len(records),
            "same_shape_residual_add": 16,
            "broadcast_bias_add": 1,
            "lifetime_edges_checked": len(related_edges),
            "lifetime_stages_checked": len(stage_records),
        },
        "instance_manifest_sha256": _canonical_sha256(records),
        "affine_reassociation_counterexamples": actual_counterexamples,
        "dependency_on_quant_tail": dependency.get("dependency_id"),
        "p0a_decision": p0a_receipt.get("decision"),
        "current_match_rules_checked": len(
            contract.get("current_match_rule_dependencies", [])
        ),
        "materialization_allowed": False,
    }
    return report
