"""Fail-closed node0071-D to node0075-A metadata-alias integration.

The approved node0072 DequantizeLinear + node0073 View + node0074
QuantizeLinear paired elimination is consumed as a frozen proof.  This module
does not repeat its binary32 analysis and does not invent a node0075 physical
consumer.  It materializes the graph/allocation overlay that is already
justified, then records the exact missing native consumer boundary.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "resnet50-node0071-node0075-uint8-identity-alias-integration-v1"
REPORT_SCHEMA = f"{SCHEMA}-report"
TEST_ID = "r5-node0071-node0075-uint8-identity-alias-integration-v1"
PROVENANCE_OWNER = "019fa2c1-17df-7122-bcbd-a727aaf173f5"
RETURN_TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"

SOURCE_TENSOR_ID = "tensor-ab32f279540568c3"
CONSUMER_TENSOR_ID = "tensor-6fbd5707d5f08110"
STORAGE_ID = (
    "r5:activation:node-0071:D:tensor-ab32f279540568c3:"
    "batch-slice-sharded-16x2048-v1"
)
ALLOCATION_OWNER = "r5:hwop-0071-01:D"
ORDERED_ADDRESS_SHA256 = (
    "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
)
WRITTEN_BYTE_SET_SHA256 = (
    "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
)

LOCKED_SHA256 = {
    "contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json":
        "7f9dbfa7d92a70c310c04275ee7c1f90dfa763de975d68bf663d3f20cbc073db",
    "artifacts/operator_config_validation/r5-quantize-node0074-dq-view-q-identity-fusion-v1/report.json":
        "213ff272db06229451f2ccd5ca53c5533698dcfc8c28b14bf2cc189fe60ea8f8",
    ".agents/task_records/20260803_quantize_node0074_dq_view_q_identity_fusion.md":
        "3a63fd8b9403d35d5e8f76a89fd4faf812649f91767cfc71ebe59ffc3b0167f0",
    "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json":
        "04e3e6e7c5b27878cb021b653c1f6ec0df16b9a5530fdd11452bfe6eb2fcf89c",
    "contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json":
        "9a832711eccd406d32ce802268889ecd67a9944a841d8cd8445af206ec93c2b0",
    "contracts/resnet50_r5_lowering_bundle.json":
        "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432",
    "contracts/operator_config/stage_config_system_v1.json":
        "79aa86fc958a2394c5161229378e490472bd5ea4273e40ea5d2139294038cf1e",
    "contracts/operator_config/stage_state_lifetime_contract_v1.json":
        "67f8e7758128a0dfea4b3faf2eab700b01b602ca052c3301fec967d6d2604744",
}

RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/Flatten_View算子配置规则.md",
    ".agents/rules/INT8_SA点积专项规则.md",
]

NATIVE_CONSUMER_CANDIDATES = [
    "ndp-sim/model_execplan/op_json/MatMulInt32Accumulate.json",
    "ndp-sim/model_execplan/op_json/QLinearMatMul.json",
]


class AliasIntegrationError(ValueError):
    """Raised when the endpoint overlay would widen an unproved claim."""


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
        raise AliasIntegrationError(f"JSON root must be an object: {path}")
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _locked_receipts(root: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for relative, expected in LOCKED_SHA256.items():
        path = root / relative
        identity = file_identity(path, root)
        identity["expected_sha256"] = expected
        identity["current_match"] = identity["sha256"] == expected
        if not identity["current_match"]:
            raise AliasIntegrationError(f"locked source drift: {relative}")
        receipts.append(identity)
    return receipts


def _rule_receipts(root: Path) -> list[dict[str, Any]]:
    return [file_identity(root / relative, root) for relative in RULE_PATHS]


def _request(bundle: dict[str, Any], hw_op_id: str) -> dict[str, Any]:
    for request in bundle["requests"]:
        if request["identity"]["hw_op_id"] == hw_op_id:
            return request
    raise AliasIntegrationError(f"missing typed request {hw_op_id}")


def _resolution(bundle: dict[str, Any], hw_op_id: str) -> dict[str, Any]:
    for resolution in bundle["effective_resolutions"]:
        if resolution["hw_op_id"] == hw_op_id:
            return resolution
    raise AliasIntegrationError(f"missing effective resolution {hw_op_id}")


def _stage_plan(system: dict[str, Any], hw_op_id: str) -> dict[str, Any]:
    for stage in system["stage_plans"]:
        if stage["identity"]["hw_op_id"] == hw_op_id:
            return stage
    raise AliasIntegrationError(f"missing stage plan {hw_op_id}")


def _ordered_stage(lifetime: dict[str, Any], request_id: str) -> dict[str, Any]:
    for stage in lifetime["ordered_config_plan"]["stages"]:
        if stage["request_id"] == request_id:
            return stage
    raise AliasIntegrationError(f"missing ordered lifetime stage {request_id}")


def _typed_edge(lifetime: dict[str, Any], edge_id: str) -> dict[str, Any]:
    for edge in lifetime["typed_tensor_dag"]["edges"]:
        if edge["edge_id"] == edge_id:
            return edge
    raise AliasIntegrationError(f"missing typed edge {edge_id}")


def _validate_frozen_handoff(root: Path) -> dict[str, Any]:
    fusion = load_json(
        root
        / "contracts/operator_config/"
        "quantize_node0074_dq_view_q_identity_fusion_v1.json"
    )
    report = load_json(
        root
        / "artifacts/operator_config_validation/"
        "r5-quantize-node0074-dq-view-q-identity-fusion-v1/report.json"
    )
    endpoint = fusion["endpoint_handoff"]
    source = endpoint["known_source_storage"]
    expected = {
        "storage_id": STORAGE_ID,
        "allocation_owner": ALLOCATION_OWNER,
        "dtype": "uint8",
        "source_shape": [16, 2048, 1, 1],
        "alias_shape": [16, 2048],
        "alias_byte_strides": [2048, 1],
        "alias_offset_bytes": 0,
        "active_slice_count": 16,
        "slice0_base_addr": "0x000a2000",
        "slice_address_stride_bytes": 1 << 25,
        "bytes_per_active_slice": 2048,
        "transaction_bytes": 32,
        "transactions_per_active_slice": 64,
        "total_valid_bytes": 32768,
        "ordered_address_sha256": ORDERED_ADDRESS_SHA256,
        "written_byte_set_sha256": WRITTEN_BYTE_SET_SHA256,
    }
    for key, value in expected.items():
        if source.get(key) != value:
            raise AliasIntegrationError(f"frozen handoff changed: {key}")
    if (
        fusion["status"] != "APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER"
        or fusion["reuse_class"] != "APPROVED_EQUIVALENT"
        or fusion["graph_rewrite"]["typed_rewrite_closed"] is not True
        or fusion["graph_rewrite"]["physical_integration_closed"] is not False
        or report.get("passed") is not True
        or report["analysis_accounting"]["numeric_analysis_repeated"] is not True
    ):
        raise AliasIntegrationError("identity-fusion approval boundary changed")
    if endpoint["provisional_address_allowed"] is not False:
        raise AliasIntegrationError("provisional consumer address became allowed")
    return {
        "approval": "APPROVED_EQUIVALENT",
        "numeric_analysis_repeated_by_this_integration": False,
        "fusion_report_consumed_without_recalculation": True,
        "known_source_storage": source,
        "original_edge_gate": endpoint["original_edge_gate"],
    }


def _typed_consumer(root: Path) -> dict[str, Any]:
    bundle = load_json(root / "contracts/resnet50_r5_lowering_bundle.json")
    request = _request(bundle, "hwop-0075-00")
    resolution = _resolution(bundle, "hwop-0075-00")
    port = next(port for port in request["ports"]["inputs"] if port["role"] == "a")
    geometry = request["logical_geometry"]
    if (
        request["request_id"] != "r5:hwop-0075-00"
        or request["ordinal"] != 129
        or request["request_sha256"]
        != "67453b2893d8dcee976f871f21e35313d08949a45779c2a8aecc4e31d6c24553"
        or request["identity"]["hw_op_type"] != "MatMulInt32Accumulate"
        or port["tensor_id"] != CONSUMER_TENSOR_ID
        or port["dtype"] != "uint8"
        or port["shape"] != [16, 2048]
        or geometry["mnk"] != {"M": 16, "N": 1000, "K": 2048}
    ):
        raise AliasIntegrationError("node0075 typed A consumer changed")
    return {
        "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "request_sha256": request["request_sha256"],
        "node_id": request["identity"]["node_id"],
        "onnx_op_type": request["identity"]["onnx_op_type"],
        "hw_op_type": request["identity"]["hw_op_type"],
        "a_port": port,
        "mnk": geometry["mnk"],
        "emission_policy": request["emission_policy"],
        "effective_resolution": resolution,
    }


def _materializer_closure(root: Path) -> dict[str, Any]:
    stage_system = load_json(
        root / "contracts/operator_config/stage_config_system_v1.json"
    )
    lifetime = load_json(
        root / "contracts/operator_config/stage_state_lifetime_contract_v1.json"
    )
    stage = _stage_plan(stage_system, "hwop-0075-00")
    ordered = _ordered_stage(lifetime, "r5:hwop-0075-00")
    edge = _typed_edge(
        lifetime,
        "r5:hwop-0074-00->r5:hwop-0075-00:tensor-6fbd5707d5f08110",
    )
    missing = [
        relative for relative in NATIVE_CONSUMER_CANDIDATES
        if not (root / relative).exists()
    ]
    operator_info_path = (
        root / "ndp-sim/model_execplan/config/operator_base_info.json"
    )
    registers_path = (
        root
        / "ndp-sim/model_execplan/src/execution_plan_generator/"
        "control_registers.py"
    )
    operator_info_text = operator_info_path.read_text(encoding="utf-8")
    registers_text = registers_path.read_text(encoding="utf-8")
    registry_hits = {
        name: {
            "operator_base_info": name in operator_info_text,
            "control_registers": name in registers_text,
        }
        for name in ("MatMulInt32Accumulate", "QLinearMatMul")
    }
    native_consumer_present = (
        not missing
        and any(
            hit["operator_base_info"] and hit["control_registers"]
            for hit in registry_hits.values()
        )
    )
    if native_consumer_present:
        raise AliasIntegrationError(
            "native node0075 consumer appeared; this blocked overlay must be rebuilt"
        )
    if (
        stage["readiness"] != "blocked"
        or any(stage["readiness_axes"].values())
        or ordered["config_transition"] != "blocked_before_config_encoding"
        or ordered["address_alias_or_copy_decision_available"] is not False
        or ordered["buffer_allocation_available"] is not False
        or ordered["lifetime_release_available"] is not False
        or edge["physical_allocation_status"]
        != "blocked_until_address_offset_and_lifetime_are_bound"
    ):
        raise AliasIntegrationError("node0075 fail-closed materializer state changed")
    return {
        "final_materialized_node0075_a_consumer_present": False,
        "missing_native_candidates": missing,
        "registry_hits": registry_hits,
        "registry_sources": [
            file_identity(operator_info_path, root),
            file_identity(registers_path, root),
        ],
        "stage_config": {
            "readiness": stage["readiness"],
            "readiness_axes": stage["readiness_axes"],
            "candidate_blockers": stage["candidate_blockers"],
        },
        "ordered_lifetime_stage": ordered,
        "typed_edge": edge,
    }


def _slice_requirements() -> list[dict[str, Any]]:
    return [
        {
            "slice_id": slice_id,
            "required_base_addr": f"0x{0x000A2000 + (slice_id << 25):08x}",
            "required_bytes": 2048,
            "required_transaction_bytes": 32,
            "required_transaction_count": 64,
            "consumer_occurrence_addresses": None,
            "consumer_ordered_address_sha256": None,
            "consumer_read_byte_set_sha256": None,
            "consumer_accepted_witness": None,
        }
        for slice_id in range(16)
    ]


def build_contract(root: Path) -> dict[str, Any]:
    locked = _locked_receipts(root)
    rules = _rule_receipts(root)
    handoff = _validate_frozen_handoff(root)
    consumer = _typed_consumer(root)
    closure = _materializer_closure(root)
    overlay = {
        "overlay_id": "r5:node0071-D->node0075-A:uint8-metadata-alias-v1",
        "status": "GRAPH_METADATA_AND_ALLOCATION_REQUIREMENT_MATERIALIZED",
        "installed_in_native_execplan": False,
        "source_tensor": {
            "tensor_id": SOURCE_TENSOR_ID,
            "dtype": "uint8",
            "shape": [16, 2048, 1, 1],
            "byte_strides": [2048, 1, 1, 1],
        },
        "consumer_tensor": {
            "tensor_id": CONSUMER_TENSOR_ID,
            "dtype": "uint8",
            "shape": [16, 2048],
            "byte_strides": [2048, 1],
        },
        "index_map": "[n,c,0,0] -> [n,c]",
        "storage_offset_bytes": 0,
        "storage_id": STORAGE_ID,
        "allocation_owner": ALLOCATION_OWNER,
        "allocation_owner_changed": False,
        "new_allocation_created": False,
        "relocation_used": False,
        "copy_used": False,
        "replay_used": False,
        "host_tensor_used": False,
        "removed_arithmetic_stages": [
            "r5:hwop-0072-00 DequantizeLinear arithmetic",
            "r5:hwop-0074-00 QuantizeLinear arithmetic",
        ],
        "metadata_only_view_preserved": True,
        "old_fp32_131072_byte_endpoint_used": False,
    }
    coverage = {
        "status": "BLOCKED_MISSING_FINAL_MATERIALIZED_NODE0075_A_CONSUMER",
        "required_total_read_bytes": 32768,
        "required_ordered_address_sha256": ORDERED_ADDRESS_SHA256,
        "required_read_byte_set_sha256": WRITTEN_BYTE_SET_SHA256,
        "required_slice_records": _slice_requirements(),
        "final_consumer_occurrence_count": None,
        "final_consumer_address_equation": None,
        "final_consumer_ordered_address_sha256": None,
        "final_consumer_read_byte_set_sha256": None,
        "coverage_proven": False,
        "producer_base_projection_accepted_as_consumer_address": False,
        "reason": (
            "node0075 has a typed A port but no final JSON/registered handler/"
            "mapping/bitstream/execplan/SCA from which A occurrences can be inverted"
        ),
    }
    lifetime = {
        "status": "REQUIREMENT_MATERIALIZED_WITNESS_BLOCKED_WITH_CONSUMER",
        "first_legal_read_requirement": (
            "node0071 final D byte-set accepted AND node0071 completion/final "
            "barrier accepted"
        ),
        "release_requirement": (
            "node0075 final A input-data accepted AND no pending/replayed read"
        ),
        "conservative_release_fallback": "node0075 completion accepted",
        "producer_visibility_witness_accepted": True,
        "cross_operator_visibility_barrier_materialized": False,
        "consumer_first_read_accepted_witness": None,
        "consumer_final_input_data_accepted_witness": None,
        "pending_or_replayed_read_empty_witness": None,
        "allocation_release_witness": None,
        "allocation_kept_owned_by": ALLOCATION_OWNER,
    }
    first_divergence = {
        "id": "B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING",
        "stage": "r5:hwop-0075-00 / ordinal 129 / A input",
        "kind": "WAIT_NODE0075_MATERIALIZER_CAPABILITY",
        "first_missing_asset": (
            "final registered MatMulInt32Accumulate/QLinearMatMul op-json handler "
            "capable of materializing node0075 A read occurrences"
        ),
        "before": (
            "approved typed uint8 identity alias and exact node0071-owned storage "
            "requirements"
        ),
        "after": (
            "node0075 A occurrence address equation, mapping, bitstream, execplan/"
            "SCA, accepted-read terminal and release witness"
        ),
        "not_yet_an_rtl_first_divergence": True,
    }
    return {
        "schema": SCHEMA,
        "test_id": TEST_ID,
        "status": "ALIAS_OVERLAY_READY_EXECPLAN_BINDING_BLOCKED",
        "provenance": {
            "analysis_owner_thread": PROVENANCE_OWNER,
            "return_target_thread": RETURN_TARGET,
        },
        "input_receipts": {
            "locked_current_match": locked,
            "active_rules_and_plan": rules,
        },
        "rule_ids": [
            "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-VIEW-METADATA-ONLY-001",
            "CDA-VIEW-PHYSICAL-IDENTITY-001",
            "CDA-VIEW-ENDPOINT-COVERAGE-001",
            "CDA-VIEW-ACCEPTED-LIFETIME-001",
            "CDA-VIEW-INTEGRATED-CLAIM-BOUNDARY-001",
        ],
        "frozen_handoff": handoff,
        "typed_node0075_consumer": consumer,
        "alias_overlay_materialization": overlay,
        "node0075_consumer_address_coverage": coverage,
        "visibility_and_lifetime": lifetime,
        "materializer_closure": closure,
        "first_divergence": first_divergence,
        "blocker_delta": {
            "B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING": "REMAINS_OPEN",
            "new_precise_sub_blocker": first_divergence["id"],
            "generic_exact_divider_blockers": "OPEN_BUT_OFF_THIS_FROZEN_PATH",
            "node0075_sa_matmul_arithmetic_blockers": "OPEN_DOWNSTREAM_NOT_RETESTED",
            "node0075_requant_and_e4_e5": "OPEN_DOWNSTREAM_NOT_RETESTED",
        },
        "canonical_patch_handoff": {
            "canonical_modified": False,
            "foreign_owner_sections_modified": False,
            "reason": (
                "top-level endpoint gate cannot close until final node0075 consumer "
                "addresses and accepted lifetime are materialized"
            ),
            "future_patch_scope_after_materializer_exists": [
                "install this metadata alias overlay in graph/allocator/execplan",
                "bind every final node0075 A occurrence to the 16 node0071 slice bases",
                "prove consumer ordered-address/read-byte-set hashes",
                "bind producer-final barrier to first accepted consumer read",
                "bind last accepted/no-replay consumer read to allocation release",
                "then close only B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING",
            ],
        },
        "analysis_accounting": {
            "numeric_analysis_repeated": False,
            "binary32_domain_retested": False,
            "w3_retested": False,
            "dequant_view_rec_counterexample_retested": False,
            "consumed_reuse_assets": True,
            "node0075_workload_built": False,
        },
        "outputs": {
            "metadata_alias_overlay_contract": True,
            "target_json": False,
            "mapping": False,
            "bitstream": False,
            "execplan": False,
            "sca": False,
            "server_package": False,
        },
        "functional_rtl_modified": False,
        "plan_or_public_rules_modified": False,
        "server_inspected_uploaded_or_run": False,
        "rule_delta_proposal": {
            "required": False,
            "reason": "current typed-edge/view/coverage/lifetime rules are sufficient",
        },
        "package_release": "NONE",
        "wait_state": "WAIT_NODE0075_MATERIALIZER_CAPABILITY",
        "claim_boundary": (
            "Machine-consumable graph/allocation metadata overlay and exact "
            "fail-closed handoff only; no node0075 physical address coverage, "
            "integrated E2, SA/MatMul arithmetic closure, E3/E4/E5, or package."
        ),
    }


def validate_contract_value(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    if contract.get("schema") != SCHEMA or contract.get("test_id") != TEST_ID:
        raise AliasIntegrationError("contract identity changed")
    if contract["provenance"] != {
        "analysis_owner_thread": PROVENANCE_OWNER,
        "return_target_thread": RETURN_TARGET,
    }:
        raise AliasIntegrationError("thread provenance changed")
    overlay = contract["alias_overlay_materialization"]
    forbidden = (
        overlay["allocation_owner_changed"],
        overlay["new_allocation_created"],
        overlay["relocation_used"],
        overlay["copy_used"],
        overlay["replay_used"],
        overlay["host_tensor_used"],
        overlay["old_fp32_131072_byte_endpoint_used"],
    )
    if any(forbidden) or overlay["installed_in_native_execplan"]:
        raise AliasIntegrationError("metadata-only/no-relocation boundary widened")
    coverage = contract["node0075_consumer_address_coverage"]
    if (
        coverage["coverage_proven"]
        or coverage["producer_base_projection_accepted_as_consumer_address"]
        or coverage["final_consumer_address_equation"] is not None
        or any(
            row["consumer_occurrence_addresses"] is not None
            for row in coverage["required_slice_records"]
        )
    ):
        raise AliasIntegrationError("unmaterialized consumer coverage was claimed")
    lifetime = contract["visibility_and_lifetime"]
    if (
        lifetime["cross_operator_visibility_barrier_materialized"]
        or lifetime["consumer_first_read_accepted_witness"] is not None
        or lifetime["allocation_release_witness"] is not None
    ):
        raise AliasIntegrationError("unmaterialized lifetime was claimed")
    if (
        contract["canonical_patch_handoff"]["canonical_modified"]
        or contract["canonical_patch_handoff"]["foreign_owner_sections_modified"]
        or contract["package_release"] != "NONE"
        or contract["wait_state"] != "WAIT_NODE0075_MATERIALIZER_CAPABILITY"
        or contract["functional_rtl_modified"]
        or contract["plan_or_public_rules_modified"]
        or contract["server_inspected_uploaded_or_run"]
    ):
        raise AliasIntegrationError("claim, ownership, or package boundary widened")
    expected = build_contract(root)
    if canonical_sha256(contract) != canonical_sha256(expected):
        raise AliasIntegrationError("contract does not current-match rebuilt overlay")
    return {
        "schema": REPORT_SCHEMA,
        "test_id": TEST_ID,
        "status": contract["status"],
        "passed": True,
        "input_receipts": contract["input_receipts"],
        "alias_overlay_materialization": overlay,
        "node0075_consumer_address_coverage": coverage,
        "visibility_and_lifetime": lifetime,
        "materializer_closure": contract["materializer_closure"],
        "first_divergence": contract["first_divergence"],
        "blocker_delta": contract["blocker_delta"],
        "canonical_patch_handoff": contract["canonical_patch_handoff"],
        "analysis_accounting": contract["analysis_accounting"],
        "outputs": contract["outputs"],
        "rule_delta_proposal": contract["rule_delta_proposal"],
        "package_release": contract["package_release"],
        "wait_state": contract["wait_state"],
        "claim_boundary": contract["claim_boundary"],
    }


def negative_control_results(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    mutations = {
        "producer_base_projection_as_consumer": (
            "node0075_consumer_address_coverage",
            "producer_base_projection_accepted_as_consumer_address",
            True,
        ),
        "relocate_allocation": (
            "alias_overlay_materialization",
            "relocation_used",
            True,
        ),
        "host_copy": ("alias_overlay_materialization", "copy_used", True),
        "premature_coverage_close": (
            "node0075_consumer_address_coverage",
            "coverage_proven",
            True,
        ),
        "premature_lifetime_close": (
            "visibility_and_lifetime",
            "cross_operator_visibility_barrier_materialized",
            True,
        ),
        "foreign_owner_write": (
            "canonical_patch_handoff",
            "foreign_owner_sections_modified",
            True,
        ),
    }
    results: dict[str, Any] = {}
    for name, (section, field, value) in mutations.items():
        candidate = copy.deepcopy(contract)
        candidate[section][field] = value
        failed_closed = False
        error = None
        try:
            validate_contract_value(candidate, root)
        except AliasIntegrationError as exc:
            failed_closed = True
            error = str(exc)
        results[name] = {"fail_closed": failed_closed, "error": error}
    if not all(result["fail_closed"] for result in results.values()):
        raise AliasIntegrationError("one or more negative controls did not fail closed")
    return results


def validate_contract(path: Path, root: Path) -> dict[str, Any]:
    contract = load_json(path)
    report = validate_contract_value(contract, root)
    report["contract"] = file_identity(path, root)
    report["negative_controls"] = negative_control_results(contract, root)
    return report


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
