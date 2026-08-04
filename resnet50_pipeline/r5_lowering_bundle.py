from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndp_patch_toolchain import validate_patchset_manifest
from .r5_resolution_overlay import blocker_resolution, validate_r5_resolution_overlay
from .stage_operator_semantics_audit import (
    GA_INT8_MAX_FLOW_BLOCKER,
    GA_INT8_MAX_NUMERIC_BLOCKER,
    GA_INT32_TO_FP32_DOMAIN_BLOCKER,
    GAP_D_INDEX_BLOCKER,
    GAP_GA_ACCUM_STATE_BLOCKER,
    SA_INT8_CSA_NUMERIC_BLOCKER,
    validate_stage_operator_semantics_audit,
)
from .typed_config_parameters import validate_typed_config_parameter_contract


BUNDLE_SCHEMA = "resnet50-r5-typed-lowering-bundle-v1"
REQUEST_SCHEMA = "resnet50-r5-typed-lowering-request-v1"
EXPECTED_STAGE_COUNT = 133
EXPECTED_NODE_COUNT = 78


class R5LoweringBundleError(ValueError):
    pass


_RTL_SEMANTIC_BLOCKERS = {
    "MaxPoolUint8": [
        GA_INT8_MAX_NUMERIC_BLOCKER,
        GA_INT8_MAX_FLOW_BLOCKER,
    ],
    "GlobalAverageSumInt32": [
        GAP_D_INDEX_BLOCKER,
        GAP_GA_ACCUM_STATE_BLOCKER,
    ],
    "RequantizeUint8": [GA_INT32_TO_FP32_DOMAIN_BLOCKER],
    "AverageRequantizeUint8": [GA_INT32_TO_FP32_DOMAIN_BLOCKER],
    "ConvInt32Accumulate": [SA_INT8_CSA_NUMERIC_BLOCKER],
    "MatMulInt32Accumulate": [SA_INT8_CSA_NUMERIC_BLOCKER],
}

_BLOCKER_FINDINGS = {
    GA_INT8_MAX_NUMERIC_BLOCKER: "CDA-GA-INT8-MAX-PIPE-001",
    GA_INT8_MAX_FLOW_BLOCKER: "CDA-GA-INT8-MAX-PIPE-001",
    GA_INT32_TO_FP32_DOMAIN_BLOCKER: "CDA-GA-INPORT-CONVERT-001",
    GAP_D_INDEX_BLOCKER: "CDA-GAP-D-INDEX-001",
    GAP_GA_ACCUM_STATE_BLOCKER: "CDA-GAP-GA-ACCUM-STATE-001",
    SA_INT8_CSA_NUMERIC_BLOCKER: "CDA-SA-INT8-CSA-001",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R5LoweringBundleError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise R5LoweringBundleError(f"required lowering input is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _request_payload(
    hw_op: Mapping[str, Any],
    *,
    ordinal: int,
    patchset: Mapping[str, Any],
) -> dict[str, Any]:
    blockers = sorted(
        {
            str(blocker)
            for binding in hw_op["field_bindings"]
            for blocker in binding.get("blockers", [])
        }
    )
    return {
        "schema": REQUEST_SCHEMA,
        "request_id": f"r5:{hw_op['hw_op_id']}",
        "ordinal": ordinal,
        "patchset": {
            "patchset_id": patchset["patchset_id"],
            "patchset_sha256": patchset["patchset_sha256"],
            "base_commit": patchset["base_commit"],
        },
        "target_profile": patchset["target_profile"],
        "identity": {
            "hw_op_id": hw_op["hw_op_id"],
            "node_id": hw_op["node_id"],
            "onnx_name": hw_op["onnx_name"],
            "onnx_op_type": hw_op["onnx_op_type"],
            "hw_op_type": hw_op["hw_op_type"],
            "stage": hw_op["stage"],
        },
        "predecessor_hw_op_ids": hw_op["predecessor_hw_op_ids"],
        "logical_geometry": hw_op["logical_geometry"],
        "ports": hw_op["ports"],
        "typed_parameters": hw_op["parameters"],
        "field_requirements": hw_op["field_bindings"],
        "emission_policy": {
            "formal_target_instance_allowed": hw_op[
                "formal_target_instance_allowed"
            ],
            "unresolved_blockers": blockers,
            "candidate_files_may_satisfy_request": False,
            "fail_closed": True,
        },
    }


def build_r5_lowering_bundle(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    typed_path = root / "contracts/typed_config_parameter_contract.json"
    graph_path = root / "artifacts/w3/model_graph.json"
    patchset_path = root / "contracts/ndp_patch_toolchain_v1.json"
    runtime_path = root / "artifacts/w3/golden_batch16/manifest.json"
    subop_path = root / "artifacts/w3/subop_batch16/manifest.json"
    overlay_path = root / "contracts/resnet50_r5_resolution_overlay.json"
    audit_path = (
        root
        / "contracts/operator_config/stage_operator_semantics_audit_v1.json"
    )

    typed = _load(typed_path)
    graph = _load(graph_path)
    patchset = _load(patchset_path)
    overlay = _load(overlay_path)
    audit = _load(audit_path)
    validate_typed_config_parameter_contract(typed)
    validate_patchset_manifest(patchset, root / "ndp-sim")
    validate_r5_resolution_overlay(overlay, root)
    validate_stage_operator_semantics_audit(root, audit_path)
    finding_classes = {
        str(item.get("issue_id")): str(item.get("classification"))
        for item in audit.get("findings", [])
        if isinstance(item, Mapping)
    }
    for blocker, finding_id in _BLOCKER_FINDINGS.items():
        if finding_classes.get(finding_id) != "CONTRADICTED":
            raise R5LoweringBundleError(
                f"RTL semantic blocker lacks contradicted audit finding: "
                f"{blocker} -> {finding_id}"
            )

    hw_ops = typed.get("hw_ops")
    if not isinstance(hw_ops, list) or len(hw_ops) != EXPECTED_STAGE_COUNT:
        raise R5LoweringBundleError("typed lowering does not contain 133 stages")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != EXPECTED_NODE_COUNT:
        raise R5LoweringBundleError("model graph does not contain 78 nodes")

    requests: list[dict[str, Any]] = []
    seen: set[str] = set()
    node_stages: dict[str, list[str]] = {}
    aggregate_lines: list[str] = []
    blocker_counts: Counter[str] = Counter()
    effective_blocker_counts: Counter[str] = Counter()
    effective_resolutions: list[dict[str, Any]] = []
    for ordinal, hw_op in enumerate(hw_ops):
        if not isinstance(hw_op, Mapping):
            raise R5LoweringBundleError(f"malformed typed stage at ordinal {ordinal}")
        hw_op_id = str(hw_op["hw_op_id"])
        if hw_op_id in seen:
            raise R5LoweringBundleError(f"duplicate typed stage: {hw_op_id}")
        predecessors = [str(value) for value in hw_op["predecessor_hw_op_ids"]]
        unknown = [value for value in predecessors if value not in seen]
        if unknown:
            raise R5LoweringBundleError(
                f"stage predecessor is missing or not topological: {hw_op_id}: {unknown}"
            )
        payload = _request_payload(hw_op, ordinal=ordinal, patchset=patchset)
        request_sha256 = sha256_bytes(canonical_json_bytes(payload))
        record = {**payload, "request_sha256": request_sha256}
        requests.append(record)
        seen.add(hw_op_id)
        node_stages.setdefault(str(hw_op["node_id"]), []).append(hw_op_id)
        aggregate_lines.append(f"{ordinal:03d}\0{hw_op_id}\0{request_sha256}")
        blocker_counts.update(payload["emission_policy"]["unresolved_blockers"])
        resolved: dict[str, str] = {}
        unresolved: list[str] = []
        for blocker in payload["emission_policy"]["unresolved_blockers"]:
            resolution = blocker_resolution(overlay, blocker, hw_op_id)
            if resolution is None:
                unresolved.append(blocker)
            else:
                resolved[blocker] = str(resolution["resolution_id"])
        local_lowering_resolved = not unresolved
        zero_copy = hw_op["hw_op_type"] == "View"
        semantic_blockers = sorted(
            _RTL_SEMANTIC_BLOCKERS.get(str(hw_op["hw_op_type"]), [])
        )
        if (
            hw_op_id == "hwop-0001-01"
            and blocker_resolution(
                overlay, "B_REQUANT_TARGET_NUMERICS", hw_op_id
            )
            is not None
        ):
            # The exact node-0001 candidate does not exercise the contradicted
            # direct negative INT32->FP32 requant path.  Its hash-bound local
            # E2 inserts an SFU sign guard first and proves all 48 final
            # bitstreams plus the complete W3 tensor.  Keep the global
            # Requant family blocker for every other stage.
            semantic_blockers = [
                blocker
                for blocker in semantic_blockers
                if blocker != GA_INT32_TO_FP32_DOMAIN_BLOCKER
            ]
        effective_blockers = sorted(set(unresolved) | set(semantic_blockers))
        effective_blocker_counts.update(effective_blockers)
        json_emitter_ready = local_lowering_resolved and not zero_copy
        rtl_semantics_compatible = (
            local_lowering_resolved and not semantic_blockers
        )
        dynamic_release_ready = (
            json_emitter_ready
            and rtl_semantics_compatible
            and hw_op["formal_target_instance_allowed"] is True
        )
        candidate_config_allowed = (
            json_emitter_ready and rtl_semantics_compatible
        )
        effective_resolutions.append(
            {
                "request_id": record["request_id"],
                "hw_op_id": hw_op_id,
                "resolved_blockers": dict(sorted(resolved.items())),
                "unresolved_blockers": unresolved,
                "rtl_semantic_blockers": semantic_blockers,
                "effective_blockers": effective_blockers,
                "local_lowering_resolved": local_lowering_resolved,
                "readiness_axes": {
                    "json_emitter_ready": json_emitter_ready,
                    "rtl_semantics_compatible": rtl_semantics_compatible,
                    "dynamic_release_ready": dynamic_release_ready,
                },
                "disposition": (
                    "candidate_config_emission_allowed"
                    if candidate_config_allowed
                    else "draft_json_emitter_ready_rtl_semantics_blocked"
                    if json_emitter_ready
                    else "candidate_zero_copy_binding_allowed"
                    if local_lowering_resolved
                    else "blocked_by_unresolved_local_semantics"
                ),
                "candidate_config_emission_allowed": candidate_config_allowed,
                "candidate_zero_copy_binding_allowed": local_lowering_resolved and zero_copy,
                "candidate_files_may_satisfy_request": candidate_config_allowed,
                "formal_target_instance_allowed": False,
                "formal_release_blockers": (
                    sorted(set(effective_blockers) | {"B_SERVER_E4_E5"})
                    if local_lowering_resolved
                    else effective_blockers
                ),
            }
        )

    graph_node_ids = [str(item["node_id"]) for item in nodes]
    if list(node_stages) != graph_node_ids:
        raise R5LoweringBundleError("lowering request node order differs from model graph")

    node_dags = [
        {
            "node_id": node_id,
            "stage_ids": stage_ids,
            "internal_edges": [
                [stage_ids[index - 1], stage_ids[index]]
                for index in range(1, len(stage_ids))
            ],
        }
        for node_id, stage_ids in node_stages.items()
    ]
    formal_ready = sum(
        bool(item["emission_policy"]["formal_target_instance_allowed"])
        for item in requests
    )
    local_resolved = sum(
        bool(item["local_lowering_resolved"]) for item in effective_resolutions
    )
    candidate_config_ready = sum(
        bool(item["candidate_config_emission_allowed"])
        for item in effective_resolutions
    )
    candidate_zero_copy_ready = sum(
        bool(item["candidate_zero_copy_binding_allowed"])
        for item in effective_resolutions
    )
    json_emitter_ready = sum(
        bool(item["readiness_axes"]["json_emitter_ready"])
        for item in effective_resolutions
    )
    rtl_semantics_compatible = sum(
        bool(item["readiness_axes"]["rtl_semantics_compatible"])
        for item in effective_resolutions
    )
    dynamic_release_ready = sum(
        bool(item["readiness_axes"]["dynamic_release_ready"])
        for item in effective_resolutions
    )
    return {
        "schema": BUNDLE_SCHEMA,
        "status": "typed_requests_complete_local_resolution_partial_formal_release_blocked",
        "inputs": {
            "typed_parameter_contract": _binding(
                root, "contracts/typed_config_parameter_contract.json"
            ),
            "model_graph": _binding(root, "artifacts/w3/model_graph.json"),
            "runtime_golden": _binding(
                root, "artifacts/w3/golden_batch16/manifest.json"
            ),
            "subop_golden": _binding(
                root, "artifacts/w3/subop_batch16/manifest.json"
            ),
            "patchset": _binding(root, "contracts/ndp_patch_toolchain_v1.json"),
            "resolution_overlay": _binding(
                root, "contracts/resnet50_r5_resolution_overlay.json"
            ),
            "stage_operator_semantics_audit": _binding(
                root,
                "contracts/operator_config/"
                "stage_operator_semantics_audit_v1.json",
            ),
        },
        "model_sha256": graph["model_sha256"],
        "patchset": {
            "patchset_id": patchset["patchset_id"],
            "patchset_sha256": patchset["patchset_sha256"],
            "base_commit": patchset["base_commit"],
        },
        "target_profile": patchset["target_profile"],
        "coverage": {
            "node_count": len(node_dags),
            "stage_count": len(requests),
            "request_count": len(requests),
            "formal_target_config_ready_count": formal_ready,
            "blocked_request_count": len(requests) - formal_ready,
            "local_lowering_resolved_count": local_resolved,
            "local_lowering_unresolved_count": len(requests) - local_resolved,
            "candidate_config_emission_allowed_count": candidate_config_ready,
            "candidate_zero_copy_binding_allowed_count": candidate_zero_copy_ready,
            "json_emitter_ready_count": json_emitter_ready,
            "rtl_semantics_compatible_count": rtl_semantics_compatible,
            "dynamic_release_ready_count": dynamic_release_ready,
            "hw_op_type_counts": dict(
                sorted(Counter(item["identity"]["hw_op_type"] for item in requests).items())
            ),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "effective_unresolved_blocker_counts": dict(
                sorted(effective_blocker_counts.items())
            ),
        },
        "request_set_sha256": sha256_bytes("\n".join(aggregate_lines).encode("utf-8")),
        "node_stage_dags": node_dags,
        "requests": requests,
        "effective_resolutions": effective_resolutions,
        "consumer_contract": {
            "verify_request_sha256_before_use": True,
            "preserve_typed_parameter_dtype_shape_axis_and_value_sha256": True,
            "preserve_predecessor_order": True,
            "reject_unknown_fields_or_unresolved_blockers": True,
            "target_config_emission_requires_formal_target_instance_allowed": True,
            "candidate_config_is_not_formal_target_config": True,
            "candidate_config_requires_json_emitter_and_rtl_semantic_readiness": True,
            "dynamic_release_requires_all_three_readiness_axes": True,
            "historical_request_payload_and_hash_are_immutable": True,
            "effective_resolution_is_overlay_and_scope_bound": True,
            "view_is_zero_copy_and_does_not_emit_operator_config": True,
            "formal_release_requires_separate_e4_e5_approval": True,
        },
    }


def validate_r5_lowering_bundle(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_r5_lowering_bundle(project_root)
    if value != expected:
        raise R5LoweringBundleError(
            "R5 typed lowering bundle differs from current hash-bound inputs"
        )


__all__ = [
    "BUNDLE_SCHEMA",
    "REQUEST_SCHEMA",
    "R5LoweringBundleError",
    "build_r5_lowering_bundle",
    "validate_r5_lowering_bundle",
]
