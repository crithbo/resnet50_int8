from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes, sha256_file


CANONICAL_RELATIVE = Path(
    "contracts/operator_config/"
    "resnet50_node0071_node0072_shared_endpoint_v1.json"
)
ARTIFACT_ROOT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-dequant-node0072-shared-endpoint-v1"
)
VALIDATION_REPORT_RELATIVE = ARTIFACT_ROOT_RELATIVE / "validation_report.json"

LOWERING_BUNDLE_RELATIVE = Path("contracts/resnet50_r5_lowering_bundle.json")
GAP_CONTRACT_RELATIVE = Path(
    "contracts/operator_config/"
    "gap_node0071_complete_config_only_local_e2_v1.json"
)
GAP_MANIFEST_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-complete-config-only-local-e2-v1/manifest.json"
)
GAP_VALIDATION_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-complete-config-only-local-e2-v1/validation_report.json"
)
GAP_ROUNDTRIP_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-complete-config-only-local-e2-v1/"
    "materialized_roundtrip_report.json"
)
GAP_SIMULATOR_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-complete-config-only-local-e2-v1/"
    "config_bound_simulator_report.json"
)
GAP_TASK_RECORD_RELATIVE = Path(
    ".agents/task_records/"
    "20260729_gap_node0071_complete_local_e2_package_ready.md"
)
GAP_PACKAGE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0071_gap_hw_v1.zip"
)
GAP_PACKAGE_VALIDATION_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0071_gap_hw_v1.validation.json"
)
GAP_V1_RETURN_ANALYSIS_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-hw-v1-return-analysis/report.json"
)
GAP_V2_PACKAGE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip"
)
GAP_V2_PACKAGE_VALIDATION_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.validation.json"
)
REUSE_POLICY_RELATIVE = Path(
    "contracts/operator_config/resnet50_reuse_first_integration_policy_v1.json"
)
GAP_RULE_RELATIVE = Path(".agents/rules/GAP_int32_mac_bypass_rules.md")
COMMON_RULE_RELATIVE = Path(".agents/rules/算子配置规则.md")
ROUTING_INDEX_RELATIVE = Path(".agents/rules/生成前必读索引.md")
PLAN_RELATIVE = Path(".agents/plan.md")

EXPECTED_SOURCE_SHA256 = {
    LOWERING_BUNDLE_RELATIVE.as_posix():
        "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432",
    GAP_CONTRACT_RELATIVE.as_posix():
        "61c6c388b64621b1df81736d4a505072755672446c863e27d10f829e214ac2bf",
    GAP_MANIFEST_RELATIVE.as_posix():
        "d457345b355c84a05639b95e0f4c5685ac974c936bef98c229afc27b57a45223",
    GAP_VALIDATION_RELATIVE.as_posix():
        "90dc38576379e4cd847367a2713863a078a00e133d8ef965b1d0fe33065b5a16",
    GAP_ROUNDTRIP_RELATIVE.as_posix():
        "63321f7af1f89ddf865ac4337862eb9f93ef5a1c893643c10996c32c2560af80",
    GAP_SIMULATOR_RELATIVE.as_posix():
        "c654d82cf2546490a01b7582195aa463d8b0032409c0435eca5222e031d413eb",
    GAP_TASK_RECORD_RELATIVE.as_posix():
        "683628ef65608689adc315a8291dd58e22c2801b469ec27fda2dfacd63bd7317",
    GAP_PACKAGE_RELATIVE.as_posix():
        "bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74",
    GAP_PACKAGE_VALIDATION_RELATIVE.as_posix():
        "f749d43ba68d055a95278ffb8fdfad60575049fea31e976c6dc93c54fa6fa229",
    GAP_V1_RETURN_ANALYSIS_RELATIVE.as_posix():
        "251971737d9a9cf09c361d87bd66cc0479f21e653ce81faa7fa7c839b3cef5f2",
    GAP_V2_PACKAGE_RELATIVE.as_posix():
        "c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f",
    GAP_V2_PACKAGE_VALIDATION_RELATIVE.as_posix():
        "f5f34434ce0f89ac0a64f6eeb9bdeac51dcf101375f3bda0519959bac3b39f5c",
    REUSE_POLICY_RELATIVE.as_posix():
        "c8886c946a15e281e2b9fc40c3e37523cc00d3aab330131572887f3d64de6960",
    GAP_RULE_RELATIVE.as_posix():
        "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
    COMMON_RULE_RELATIVE.as_posix():
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ROUTING_INDEX_RELATIVE.as_posix():
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
}

PLAN_SHA256_AT_GENERATION = (
    "ca96023deebdc274d052fb3248143a5b8a3fa3c9ba5de0bee9d793bb0fcac54d"
)
STORAGE_ID = (
    "r5:activation:node-0071:D:tensor-ab32f279540568c3:"
    "batch-slice-sharded-16x2048-v1"
)
TENSOR_ID = "tensor-ab32f279540568c3"
TENSOR_NAME = "resnetv17_pool1_fwd_quantized"
TENSOR_IDENTITY_SHA256 = (
    "70e76086c96394b1cc0a50cf316663b4ea1def7f0d0b73568dd83662d6556b55"
)
SLICE_COUNT = 16
TARGET_SLICE_COUNT = 28
BYTES_PER_SLICE = 2048
LOGICAL_BYTES = 32768
TRANSACTION_BYTES = 32
TRANSACTIONS_PER_SLICE = 64
SLICE_ADDRESS_STRIDE = 0x02000000
SLICE0_D_BASE = 0x000A2000
LOCAL_END_EXCLUSIVE = 0x000A2800
LOCAL_ORDERED_ADDRESS_SHA256 = (
    "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
)
LOCAL_WRITTEN_BYTE_SET_SHA256 = (
    "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
)


class GapDequantSharedEndpointError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapDequantSharedEndpointError(f"{path} is not a JSON object")
    return value


def _section_content_sha256(section: dict[str, Any]) -> str:
    body = deepcopy(section)
    body.pop("owner_section_content_sha256", None)
    return sha256_bytes(canonical_json_bytes(body))


def _source_map(section: dict[str, Any]) -> dict[str, str]:
    sources = section.get("immutable_sources")
    if not isinstance(sources, list):
        raise GapDequantSharedEndpointError("GAP immutable_sources is not a list")
    result: dict[str, str] = {}
    for item in sources:
        if not isinstance(item, dict):
            raise GapDequantSharedEndpointError("GAP source entry is not an object")
        path = str(item.get("path"))
        if path in result:
            raise GapDequantSharedEndpointError(
                f"duplicate GAP immutable source path: {path}"
            )
        result[path] = str(item.get("sha256"))
    return result


def _request(bundle: dict[str, Any], request_id: str) -> dict[str, Any]:
    requests = bundle.get("requests")
    if not isinstance(requests, list):
        raise GapDequantSharedEndpointError("lowering bundle requests is not a list")
    matches = [
        item
        for item in requests
        if isinstance(item, dict) and item.get("request_id") == request_id
    ]
    if len(matches) != 1:
        raise GapDequantSharedEndpointError(
            f"expected one lowering request for {request_id}"
        )
    return matches[0]


def _port(request: dict[str, Any], direction: str, index: int) -> dict[str, Any]:
    ports = request.get("ports")
    if not isinstance(ports, dict):
        raise GapDequantSharedEndpointError("lowering request ports is not an object")
    values = ports.get(direction)
    if not isinstance(values, list) or index >= len(values):
        raise GapDequantSharedEndpointError(
            f"lowering request {direction}[{index}] is absent"
        )
    value = values[index]
    if not isinstance(value, dict):
        raise GapDequantSharedEndpointError(
            f"lowering request {direction}[{index}] is not an object"
        )
    return value


def _slice_records() -> list[dict[str, Any]]:
    return [
        {
            "slice_id": slice_id,
            "physical_d_base_addr": (
                f"0x{SLICE0_D_BASE + slice_id * SLICE_ADDRESS_STRIDE:08x}"
            ),
            "allocation_byte_offset": 0,
            "physical_written_bytes": BYTES_PER_SLICE,
            "valid_logical_byte_offset": slice_id * BYTES_PER_SLICE,
            "valid_logical_bytes": BYTES_PER_SLICE,
            "physical_padding_bytes": 0,
            "transaction_bytes": TRANSACTION_BYTES,
            "transaction_count": TRANSACTIONS_PER_SLICE,
            "first_transaction_addr": (
                f"0x{SLICE0_D_BASE + slice_id * SLICE_ADDRESS_STRIDE:08x}"
            ),
            "last_transaction_addr": (
                "0x"
                f"{SLICE0_D_BASE + slice_id * SLICE_ADDRESS_STRIDE + 0x7e0:08x}"
            ),
            "end_exclusive": (
                "0x"
                f"{SLICE0_D_BASE + slice_id * SLICE_ADDRESS_STRIDE + BYTES_PER_SLICE:08x}"
            ),
            "final_written_byte_coverage_complete": True,
            "final_written_byte_coverage_unique": True,
        }
        for slice_id in range(SLICE_COUNT)
    ]


def _immutable_sources() -> list[dict[str, str]]:
    roles = {
        LOWERING_BUNDLE_RELATIVE.as_posix():
            "typed node0071-D and node0072-A handoff identity",
        GAP_CONTRACT_RELATIVE.as_posix():
            "accepted node0071 complete local E2 machine contract",
        GAP_MANIFEST_RELATIVE.as_posix():
            "accepted node0071 complete local E2 artifact manifest",
        GAP_VALIDATION_RELATIVE.as_posix():
            "accepted node0071 completion and address evidence",
        GAP_ROUNDTRIP_RELATIVE.as_posix():
            "accepted final address-bound occurrence and coverage evidence",
        GAP_SIMULATOR_RELATIVE.as_posix():
            "accepted exact uint8 config-bound payload evidence",
        GAP_TASK_RECORD_RELATIVE.as_posix():
            "mainline-accepted node0071 E2 and package-ready record",
        GAP_PACKAGE_RELATIVE.as_posix():
            "frozen existing PACKAGE_READY_NOT_RUN zip; read-only identity",
        GAP_PACKAGE_VALIDATION_RELATIVE.as_posix():
            "frozen existing package validation identity",
        GAP_V1_RETURN_ANALYSIS_RELATIVE.as_posix():
            "adjudicated v1 compile failure and fail-closed gate evidence",
        GAP_V2_PACKAGE_RELATIVE.as_posix():
            "fresh package-local observer repair candidate; not run",
        GAP_V2_PACKAGE_VALIDATION_RELATIVE.as_posix():
            "v2 deterministic build and package preflight receipt",
        REUSE_POLICY_RELATIVE.as_posix():
            "reuse-first integration policy",
        GAP_RULE_RELATIVE.as_posix():
            "GAP local E2 reuse and claim boundary authority",
        COMMON_RULE_RELATIVE.as_posix():
            "config-only and reuse-first authority",
        ROUTING_INDEX_RELATIVE.as_posix():
            "generation routing receipt",
    }
    return [
        {"path": path, "sha256": sha256, "role": roles[path]}
        for path, sha256 in EXPECTED_SOURCE_SHA256.items()
    ]


def _build_owner_section() -> dict[str, Any]:
    section: dict[str, Any] = {
        "owner_family": "QLinearGlobalAveragePool",
        "owner_node": "node-0071",
        "owner_hwop": "r5:hwop-0071-01",
        "owner_port": "D",
        "owner_section_content_sha256": "",
        "reuse_status": "REUSE_ACCEPTED_FOR_INTEGRATION",
        "reuse_class": "EXACT_FULL_OPERATOR",
        "numeric_analysis_repeated": False,
        "operator_e2_retested": False,
        "sum_or_tail_numeric_reexecuted": False,
        "package_rebuilt_or_modified": False,
        "replacement_package_generated": True,
        "consumed_reuse_assets": True,
        "immutable_sources": _immutable_sources(),
        "rule_ids": [
            "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
            "CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001",
            "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
        ],
        "typed_endpoint_identity": {
            "producer": {
                "node": "node-0071",
                "hwop": "r5:hwop-0071-01",
                "port": "D",
                "onnx_op_type": "QLinearGlobalAveragePool",
            },
            "consumer_requirement_only": {
                "node": "node-0072",
                "hwop": "r5:hwop-0072-00",
                "port": "A",
                "onnx_op_type": "DequantizeLinear",
                "owner_section_present": False,
            },
            "tensor_id": TENSOR_ID,
            "onnx_name": TENSOR_NAME,
            "identity_sha256": TENSOR_IDENTITY_SHA256,
            "identity_source": "artifacts/w3/golden_batch16/manifest.json",
            "dtype": "uint8",
            "shape": [16, 2048, 1, 1],
            "producer_and_consumer_typed_identity_exact": True,
        },
        "storage_identity": {
            "storage_id": STORAGE_ID,
            "identity_class": "BATCH_SLICE_SHARDED_ACTIVATION",
            "allocation_owner": "r5:hwop-0071-01:D",
            "tensor_id": TENSOR_ID,
            "dtype": "uint8",
            "logical_shape": [16, 2048, 1, 1],
            "logical_byte_strides": [2048, 1, 1, 1],
            "logical_element_count": 32768,
            "logical_valid_byte_span": LOGICAL_BYTES,
            "byte_offset_within_allocation": 0,
            "physical_address_space": "NDP_PER_SLICE_DDR",
            "allocation_owner_remains_producer": True,
            "consumer_may_relocate_or_repartition": False,
        },
        "base_and_offset": {
            "target_slice_count": TARGET_SLICE_COUNT,
            "active_producer_slice_count": SLICE_COUNT,
            "inactive_slice_ids": list(range(SLICE_COUNT, TARGET_SLICE_COUNT)),
            "slice0_base_addr": "0x000a2000",
            "slice_address_stride_bytes": SLICE_ADDRESS_STRIDE,
            "base_formula": "D_base(slice)=0x000a2000+(slice_id<<25), 0<=slice_id<16",
            "producer_allocation_byte_offset": 0,
            "consumer_required_view_byte_offset": 0,
            "same_storage_requires_identical_active_slice_bases": True,
            "inactive_slices_are_not_endpoint_padding": True,
        },
        "coverage": {
            "physical_written_bytes": LOGICAL_BYTES,
            "logical_valid_bytes": LOGICAL_BYTES,
            "physical_padding_bytes": 0,
            "active_slice_count": SLICE_COUNT,
            "bytes_per_active_slice": BYTES_PER_SLICE,
            "transaction_bytes": TRANSACTION_BYTES,
            "transactions_per_active_slice": TRANSACTIONS_PER_SLICE,
            "transaction_equation": (
                "addr(slice,occurrence)=0x000a2000+(slice_id<<25)+"
                "32*occurrence, 0<=slice_id<16, 0<=occurrence<64"
            ),
            "logical_mapping": (
                "logical uint8[n,c,0,0] maps to slice=n and "
                "local byte offset=c, 0<=n<16, 0<=c<2048"
            ),
            "local_first_address": "0x000a2000",
            "local_last_transaction_address": "0x000a27e0",
            "local_end_exclusive": "0x000a2800",
            "local_ordered_address_sha256": LOCAL_ORDERED_ADDRESS_SHA256,
            "local_written_byte_set_sha256": LOCAL_WRITTEN_BYTE_SET_SHA256,
            "logical_inverse_complete": True,
            "logical_inverse_unique": True,
            "slice_records": _slice_records(),
        },
        "final_accepted_write_completion": {
            "evidence_scope": "FROZEN_NODE0071_COMPLETE_LOCAL_E2_REUSED_NOT_RERUN",
            "static_validator_completion_path_accepted": True,
            "execplan_all_eight_stages_and_final_barrier_accepted": True,
            "config_bound_simulator_exact_uint8_payload_accepted": True,
            "final_round_d_all_active_slice_writes_complete": True,
            "local_readback_exact_payload_accepted": True,
            "dynamic_hardware_final_write_accepted": False,
            "integrated_node0071_to_node0072_completion_accepted": False,
        },
        "visibility_and_lifetime": {
            "producer_visibility_event": (
                "node0071 final uint8 D byte-set accepted AND "
                "node0071 completion/final barrier accepted"
            ),
            "producer_local_visibility_evidence_accepted": True,
            "consumer_first_legal_read": "after producer_visibility_event",
            "required_release_event": (
                "node0072 final A input-data accepted AND no pending/replayed "
                "read; fallback=node0072 completion accepted"
            ),
            "allocation_owner": "r5:hwop-0071-01:D",
            "producer_allocation_must_remain_live_until_required_release_event": True,
            "producer_local_readback_does_not_release_shared_endpoint": True,
            "consumer_must_materialize_first_read_acceptance_gate": True,
            "shared_multi_operator_barrier_materialized": False,
            "integrated_visibility_lifetime_status":
                "DEFERRED_TO_DEQUANT_CONSUMER_OWNER",
        },
        "consumer_match_requirements": {
            "required_owner_family": "DequantizeLinear",
            "required_node": "node-0072",
            "required_port": "A",
            "required_storage_id": STORAGE_ID,
            "required_dtype": "uint8",
            "required_shape": [16, 2048, 1, 1],
            "required_active_slice_count": SLICE_COUNT,
            "required_identical_active_slice_bases": True,
            "required_view_byte_offset": 0,
            "required_valid_read_bytes": LOGICAL_BYTES,
            "required_read_coverage_equals_producer_written_byte_set": True,
            "required_first_read_after_producer_visibility_event": True,
            "host_precomputed_internal_or_final_tensor_replay_allowed": False,
            "differing_sharding_base_or_offset_requires_explicit_consumer_owned_bridge":
                True,
            "no_differing_consumer_layout_is_declared_equivalent_here": True,
            "consumer_section_present": False,
        },
        "frozen_complete_e2_identity": {
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "evidence_level": "E2_LOCAL_COMPLETE_NODE",
            "contract_path": GAP_CONTRACT_RELATIVE.as_posix(),
            "contract_file_sha256": EXPECTED_SOURCE_SHA256[
                GAP_CONTRACT_RELATIVE.as_posix()
            ],
            "contract_semantic_sha256":
                "5d98e0493eeb8c7caa9a34e8a3cc733db8def2b01de28698b0b05c4440ac4e90",
            "artifact_manifest_path": GAP_MANIFEST_RELATIVE.as_posix(),
            "artifact_manifest_file_sha256": EXPECTED_SOURCE_SHA256[
                GAP_MANIFEST_RELATIVE.as_posix()
            ],
            "artifact_manifest_semantic_sha256":
                "c85d1b003af441700076dd001f0adb8c4d1f32ef0c50107fb55be88dbd0ee0d6",
            "validation_report_sha256": EXPECTED_SOURCE_SHA256[
                GAP_VALIDATION_RELATIVE.as_posix()
            ],
            "materialized_roundtrip_report_sha256": EXPECTED_SOURCE_SHA256[
                GAP_ROUNDTRIP_RELATIVE.as_posix()
            ],
            "config_bound_simulator_report_sha256": EXPECTED_SOURCE_SHA256[
                GAP_SIMULATOR_RELATIVE.as_posix()
            ],
            "exact_uint8_payload_sha256":
                "b0b78ce73942e90566b05edfe6bd5ca5e924d3865e0232b31a58d9ffabb41067",
            "existing_package": {
                "identity": "r5_node0071_gap_hw_v1",
                "path": GAP_PACKAGE_RELATIVE.as_posix(),
                "sha256": EXPECTED_SOURCE_SHA256[GAP_PACKAGE_RELATIVE.as_posix()],
                "size_bytes": 1766963,
                "status": "PACKAGE_READY_NOT_RUN",
                "rebuilt_or_modified_by_this_task": False,
                "dynamic_return_status":
                    "COMPILE_FAILED_NO_DYNAMIC_GAP_EVIDENCE",
                "dynamic_return_analysis_path":
                    GAP_V1_RETURN_ANALYSIS_RELATIVE.as_posix(),
                "dynamic_return_analysis_sha256": EXPECTED_SOURCE_SHA256[
                    GAP_V1_RETURN_ANALYSIS_RELATIVE.as_posix()
                ],
                "retained_read_only": True,
            },
            "replacement_candidate_package": {
                "identity": "r5_n71_gap_v2_obs",
                "path": GAP_V2_PACKAGE_RELATIVE.as_posix(),
                "sha256": EXPECTED_SOURCE_SHA256[
                    GAP_V2_PACKAGE_RELATIVE.as_posix()
                ],
                "size_bytes": 1777110,
                "status": "PACKAGE_READY_NOT_RUN",
                "repair_classification":
                    "PACKAGE_LOCAL_OBSERVER_INCLUDE_BINDING_MISSING",
                "source_numeric_payload_reused_without_rebuild": True,
                "numeric_analysis_repeated": False,
                "server_file_write_required": False,
            },
        },
        "bypass_annotation": {
            "bypass_reason": (
                "Preserve the accepted node0071 configuration-only producer "
                "while binding its output into the whole-network endpoint."
            ),
            "contradicted_or_missing_native_path": (
                "repair_v9, transout, RTL_CONTROL and CONFIG_SEMANTICS repair "
                "routes remain frozen; no native integrated node0071-to-node0072 "
                "lifecycle contract is accepted."
            ),
            "exact_equivalence_scope": (
                "Only the accepted node0071 uint8[16,2048,1,1] D storage, "
                "addresses, byte set and visibility/lifetime requirements."
            ),
            "materialized_configuration_mechanism": (
                "Owner-partition canonical metadata binds the existing "
                "address-bound GAP D allocation; it adds no compute stage."
            ),
            "performance_and_resource_cost": (
                "No new compute or scratch is added by this manifest; retaining "
                "the producer allocation through node0072 acceptance extends "
                "live memory lifetime. Any consumer bridge would add separate "
                "copy/relayout latency and storage and is not authorized here."
            ),
            "unresolved_production_blocker": (
                "Dequant consumer owner section, integrated first-read/barrier/"
                "completion acceptance, v2 dynamic execution, native "
                "integration and E4/E5 are open."
            ),
            "claim_boundary": (
                "CONFIG_ONLY_CORRECTNESS_BASELINE producer reuse only; not a "
                "closed node0071-to-node0072 endpoint, not a new E2, and not "
                "production/E3/E4/E5."
            ),
        },
        "claim_boundary": {
            "gap_complete_local_e2_preserved": True,
            "integrated_endpoint_closed": False,
            "counts_as_new_e2": False,
            "complete_onnx_local_config_only_e2_count_remains": "3/78",
            "counts_as_e3_e4_or_e5": False,
            "package_ready_not_run_count_remains": 2,
            "precise_materialized_json_count_incremented": False,
            "reason": (
                "This owner section freezes an accepted producer endpoint and "
                "does not materialize or execute a new operator."
            ),
        },
        "package_release": {
            "state": "V1_FAILED_V2_PACKAGE_READY_NOT_RUN",
            "existing_package_identity": "r5_node0071_gap_hw_v1",
            "replacement_candidate_identity": "r5_n71_gap_v2_obs",
            "new_server_package_generated": True,
            "new_package_is_operator_only_not_integrated_endpoint": True,
            "existing_package_rebuilt_or_modified": False,
            "server_files_inspected": False,
            "server_upload_or_run": False,
            "server_lease": False,
        },
    }
    section["owner_section_content_sha256"] = _section_content_sha256(section)
    return section


def build_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    for relative, expected_sha in EXPECTED_SOURCE_SHA256.items():
        actual = sha256_file(root / relative)
        if actual != expected_sha:
            raise GapDequantSharedEndpointError(
                f"immutable source drifted: {relative}: {actual} != {expected_sha}"
            )
    bundle = _read_json(root / LOWERING_BUNDLE_RELATIVE)
    producer = _port(_request(bundle, "r5:hwop-0071-01"), "outputs", 0)
    consumer = _port(_request(bundle, "r5:hwop-0072-00"), "inputs", 0)
    expected_port = {
        "dtype": "uint8",
        "identity_sha256": TENSOR_IDENTITY_SHA256,
        "identity_source": "artifacts/w3/golden_batch16/manifest.json",
        "kind": "intermediate",
        "onnx_name": TENSOR_NAME,
        "shape": [16, 2048, 1, 1],
        "tensor_id": TENSOR_ID,
    }
    producer_without_role = dict(producer)
    producer_without_role.pop("role", None)
    consumer_without_role = dict(consumer)
    consumer_without_role.pop("role", None)
    if producer_without_role != consumer_without_role:
        raise GapDequantSharedEndpointError(
            "typed node0071-D and node0072-A identities differ"
        )
    if producer_without_role != expected_port or consumer_without_role != expected_port:
        raise GapDequantSharedEndpointError("typed endpoint port identity drifted")

    gap_contract = _read_json(root / GAP_CONTRACT_RELATIVE)
    if (
        gap_contract.get("status") != "CONFIG_ONLY_CORRECTNESS_BASELINE"
        or gap_contract.get("contract_sha256")
        != "5d98e0493eeb8c7caa9a34e8a3cc733db8def2b01de28698b0b05c4440ac4e90"
        or gap_contract.get("release", {}).get("evidence_level")
        != "E2_LOCAL_COMPLETE_NODE"
    ):
        raise GapDequantSharedEndpointError("accepted GAP contract identity differs")

    roundtrip = _read_json(root / GAP_ROUNDTRIP_RELATIVE)
    final_region = roundtrip.get("regions", {}).get("final_uint8", {})
    final_coverage = roundtrip.get("occurrence_and_coverage", {}).get(
        "round_write_uint8", {}
    )
    if final_region != {
        "base": "0xa2000",
        "bytes_per_slice": BYTES_PER_SLICE,
        "consumer": "formal node0071 output readback",
        "end_exclusive": "0xa2800",
        "producer": "tail RNE D",
    }:
        raise GapDequantSharedEndpointError("accepted GAP final region differs")
    if final_coverage != {
        "end_exclusive": "0xa2800",
        "exact_region_coverage": True,
        "first_address": "0xa2000",
        "last_address": "0xa27e0",
        "ordered_address_sha256": LOCAL_ORDERED_ADDRESS_SHA256,
        "transaction_bytes": TRANSACTION_BYTES,
        "transaction_count_per_slice": TRANSACTIONS_PER_SLICE,
        "written_byte_count": BYTES_PER_SLICE,
        "written_byte_set_sha256": LOCAL_WRITTEN_BYTE_SET_SHA256,
    }:
        raise GapDequantSharedEndpointError("accepted GAP final coverage differs")
    if (
        roundtrip.get("occurrence_and_coverage", {}).get("active_slice_count")
        != SLICE_COUNT
        or roundtrip.get("occurrence_and_coverage", {}).get(
            "formal_output_bytes_all_slices"
        )
        != LOGICAL_BYTES
    ):
        raise GapDequantSharedEndpointError("accepted GAP aggregate coverage differs")

    simulator = _read_json(root / GAP_SIMULATOR_RELATIVE)
    if (
        simulator.get("valid") is not True
        or simulator.get("complete_gap_target") is not True
        or simulator.get("mismatch_count") != 0
        or simulator.get("element_count") != LOGICAL_BYTES
        or simulator.get("actual_uint8_payload_sha256")
        != "b0b78ce73942e90566b05edfe6bd5ca5e924d3865e0232b31a58d9ffabb41067"
    ):
        raise GapDequantSharedEndpointError("accepted GAP simulator identity differs")

    package_validation = _read_json(root / GAP_PACKAGE_VALIDATION_RELATIVE)
    if (
        package_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or package_validation.get("server_run_performed") is not False
        or package_validation.get("zip_sha256")
        != EXPECTED_SOURCE_SHA256[GAP_PACKAGE_RELATIVE.as_posix()]
        or package_validation.get("zip_size_bytes") != 1766963
    ):
        raise GapDequantSharedEndpointError("frozen package identity differs")
    return_analysis = _read_json(root / GAP_V1_RETURN_ANALYSIS_RELATIVE)
    if (
        return_analysis.get("status")
        != "COMPILE_FAILED_NO_DYNAMIC_GAP_EVIDENCE"
        or return_analysis.get("execution_status", {}).get(
            "compile_exit_status"
        )
        != 2
        or return_analysis.get("execution_status", {}).get(
            "formal_dynamic_readback_count"
        )
        != 0
        or return_analysis.get("endpoint_impact", {}).get(
            "producer_storage_base_offset_coverage_preserved"
        )
        is not True
    ):
        raise GapDequantSharedEndpointError(
            "node0071 v1 return adjudication differs"
        )
    v2_validation = _read_json(root / GAP_V2_PACKAGE_VALIDATION_RELATIVE)
    if (
        v2_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or v2_validation.get("zip_sha256")
        != EXPECTED_SOURCE_SHA256[GAP_V2_PACKAGE_RELATIVE.as_posix()]
        or v2_validation.get("source_numeric_payload_tree_equal") is not True
        or v2_validation.get("numeric_analysis_repeated") is not False
        or v2_validation.get("functional_rtl_modified") is not False
        or v2_validation.get("server_action") is not False
    ):
        raise GapDequantSharedEndpointError(
            "node0071 v2 package validation identity differs"
        )

    return {
        "schema": "resnet50-shared-endpoint-owner-manifest-v1",
        "date": "2026-07-29",
        "status": "PARTIAL_GAP_PRODUCER_SECTION_READY",
        "endpoint_id": "r5:endpoint:node-0071:D->node-0072:A",
        "chain": ["node-0071:D", "node-0072:A"],
        "control_plane_receipt": {
            "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
            "mutable_plan_sha256_at_generation": PLAN_SHA256_AT_GENERATION,
            "plan_is_mutable_provenance_not_semantic_gate": True,
            "common_rule_sha256": EXPECTED_SOURCE_SHA256[
                COMMON_RULE_RELATIVE.as_posix()
            ],
            "routing_index_sha256": EXPECTED_SOURCE_SHA256[
                ROUTING_INDEX_RELATIVE.as_posix()
            ],
            "gap_rule_sha256": EXPECTED_SOURCE_SHA256[
                GAP_RULE_RELATIVE.as_posix()
            ],
        },
        "owner_partition_policy": {
            "each_operator_family_writes_only_its_owned_section": True,
            "foreign_owner_sections_are_immutable": True,
            "missing_owner_sections_are_explicit": True,
            "endpoint_closes_only_after_all_owner_sections_and_cross_owner_gates_pass":
                True,
        },
        "owner_sections": {
            "QLinearGlobalAveragePool": _build_owner_section(),
        },
        "required_missing_owner_sections": ["DequantizeLinear"],
        "cross_owner_gates": {
            "typed_tensor_identity_equal": True,
            "storage_base_offset_coverage_match": "WAITING_FOR_DEQUANT_OWNER",
            "producer_visibility_to_consumer_first_read":
                "WAITING_FOR_DEQUANT_OWNER",
            "release_event_and_no_replay_read": "WAITING_FOR_DEQUANT_OWNER",
            "integrated_config_bound_e2": "NOT_RUN",
        },
        "integrated_endpoint_closed": False,
        "server_package_generated": False,
        "operator_repair_package_generated": True,
        "operator_repair_package_status": "PACKAGE_READY_NOT_RUN",
        "existing_package_rebuilt_or_modified": False,
        "server_inspected_uploaded_or_run": False,
        "numeric_analysis_repeated": False,
        "operator_e2_retested": False,
        "claim_boundary": (
            "Only the accepted GAP producer section is canonicalized. The "
            "Dequant consumer section and integrated lifecycle/config-bound "
            "E2 are missing; the full shared endpoint is not claimed."
        ),
    }


def validate_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / CANONICAL_RELATIVE)
    expected = build_manifest(root)
    if manifest != expected:
        raise GapDequantSharedEndpointError(
            "canonical shared-endpoint manifest differs from deterministic build"
        )

    sections = manifest.get("owner_sections")
    if not isinstance(sections, dict) or set(sections) != {
        "QLinearGlobalAveragePool"
    }:
        raise GapDequantSharedEndpointError(
            "canonical asset must contain only the GAP producer owner section"
        )
    section = sections["QLinearGlobalAveragePool"]
    if section.get("owner_section_content_sha256") != _section_content_sha256(
        section
    ):
        raise GapDequantSharedEndpointError("GAP owner section self-hash differs")
    if _source_map(section) != EXPECTED_SOURCE_SHA256:
        raise GapDequantSharedEndpointError("GAP immutable source set differs")

    coverage = section["coverage"]
    records = coverage.get("slice_records")
    if records != _slice_records():
        raise GapDequantSharedEndpointError("GAP slice coverage records differ")
    if (
        sum(record["physical_written_bytes"] for record in records)
        != LOGICAL_BYTES
        or sum(record["valid_logical_bytes"] for record in records)
        != LOGICAL_BYTES
        or sum(record["physical_padding_bytes"] for record in records) != 0
    ):
        raise GapDequantSharedEndpointError("GAP aggregate coverage differs")

    accepted = section["final_accepted_write_completion"]
    if (
        accepted.get("dynamic_hardware_final_write_accepted") is not False
        or accepted.get("integrated_node0071_to_node0072_completion_accepted")
        is not False
    ):
        raise GapDequantSharedEndpointError("GAP completion is overclaimed")
    lifetime = section["visibility_and_lifetime"]
    if (
        lifetime.get("shared_multi_operator_barrier_materialized") is not False
        or lifetime.get("integrated_visibility_lifetime_status")
        != "DEFERRED_TO_DEQUANT_CONSUMER_OWNER"
    ):
        raise GapDequantSharedEndpointError(
            "integrated visibility/lifetime is overclaimed"
        )
    consumer = section["consumer_match_requirements"]
    if (
        consumer.get("consumer_section_present") is not False
        or consumer.get("required_storage_id") != STORAGE_ID
        or consumer.get("required_valid_read_bytes") != LOGICAL_BYTES
        or consumer.get("required_view_byte_offset") != 0
    ):
        raise GapDequantSharedEndpointError("Dequant consumer requirement differs")
    if manifest.get("required_missing_owner_sections") != ["DequantizeLinear"]:
        raise GapDequantSharedEndpointError("missing Dequant owner section differs")
    if (
        manifest.get("integrated_endpoint_closed") is not False
        or manifest.get("server_package_generated") is not False
        or manifest.get("existing_package_rebuilt_or_modified") is not False
        or manifest.get("numeric_analysis_repeated") is not False
        or manifest.get("operator_e2_retested") is not False
    ):
        raise GapDequantSharedEndpointError("shared endpoint claim boundary differs")

    return {
        "schema": "gap-node0071-dequant-node0072-shared-endpoint-validation-v1",
        "valid": True,
        "canonical_manifest_path": CANONICAL_RELATIVE.as_posix(),
        "canonical_manifest_sha256": sha256_file(root / CANONICAL_RELATIVE),
        "gap_owner_section_sha256": section["owner_section_content_sha256"],
        "immutable_source_count": len(EXPECTED_SOURCE_SHA256),
        "typed_tensor_identity_equal": True,
        "storage_id": STORAGE_ID,
        "active_slice_count": SLICE_COUNT,
        "inactive_slice_count": TARGET_SLICE_COUNT - SLICE_COUNT,
        "bytes_per_active_slice": BYTES_PER_SLICE,
        "physical_written_bytes": LOGICAL_BYTES,
        "logical_valid_bytes": LOGICAL_BYTES,
        "physical_padding_bytes": 0,
        "base_offset_coverage_frozen": True,
        "final_write_completion_reused": True,
        "dequant_consumer_section_present": False,
        "integrated_visibility_lifetime_status":
            "DEFERRED_TO_DEQUANT_CONSUMER_OWNER",
        "numeric_analysis_repeated": False,
        "operator_e2_retested": False,
        "existing_package_sha256": EXPECTED_SOURCE_SHA256[
            GAP_PACKAGE_RELATIVE.as_posix()
        ],
        "existing_package_rebuilt_or_modified": False,
        "integrated_endpoint_closed": False,
    }


def write_outputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    package_sha_before = sha256_file(root / GAP_PACKAGE_RELATIVE)
    manifest = build_manifest(root)
    canonical_path = root / CANONICAL_RELATIVE
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = validate_manifest(root)
    package_sha_after = sha256_file(root / GAP_PACKAGE_RELATIVE)
    if package_sha_after != package_sha_before:
        raise GapDequantSharedEndpointError(
            "frozen node0071 package changed during endpoint generation"
        )
    report["existing_package_sha256_before"] = package_sha_before
    report["existing_package_sha256_after"] = package_sha_after
    report["existing_package_byte_identity_preserved"] = True
    report_path = root / VALIDATION_REPORT_RELATIVE
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = [
    "ARTIFACT_ROOT_RELATIVE",
    "CANONICAL_RELATIVE",
    "GapDequantSharedEndpointError",
    "STORAGE_ID",
    "VALIDATION_REPORT_RELATIVE",
    "build_manifest",
    "validate_manifest",
    "write_outputs",
]
