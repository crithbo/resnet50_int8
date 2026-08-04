from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-flatten-physical-view-v1"
REPORT_SCHEMA = "resnet50-flatten-physical-view-validation-v1"
CONTRACT_SCHEMA = "resnet50-flatten-physical-view-contract-v1"
BINDING_SCHEMA = "resnet50-flatten-physical-view-binding-v1"
TEST_ID = "r5-flatten-node0073-zero-copy-view-v1"
REQUEST_IDS = {
    "producer": "r5:hwop-0072-00",
    "view": "r5:hwop-0073-00",
    "consumer": "r5:hwop-0074-00",
}
TENSOR_IDS = {
    "input": "tensor-50c285690f899b1b",
    "output": "tensor-9b1363d3baf474c8",
}
INPUT_SHAPE = (16, 2048, 1, 1)
OUTPUT_SHAPE = (16, 2048)
INPUT_BYTE_STRIDES = (8192, 4, 4, 4)
OUTPUT_BYTE_STRIDES = (8192, 4)
ELEMENT_COUNT = 32768
BYTE_COUNT = 131072
ACCEPTED_EVENT_ORDER = (
    "allocation.bind_accepted",
    "node0073.view_alias_bind_accepted",
    "node0072.final_output_write_accepted",
    "node0072.completion_accepted",
    "node0074.first_input_data_accepted",
    "node0074.final_input_data_accepted",
    "allocation.release_accepted",
)
SOURCE_BINDING_KEYS = (
    "producer_addressed_execplan",
    "producer_layout_contract",
    "consumer_addressed_execplan",
    "consumer_layout_contract",
    "allocator_plan",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

LOWERING_PATH = "contracts/resnet50_r5_lowering_bundle.json"
LIFETIME_PATH = (
    "contracts/operator_config/stage_state_lifetime_contract_v1.json"
)
GOLDEN_MANIFEST_PATH = "artifacts/w3/golden_batch16/manifest.json"
RULE_PATHS = (
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/Flatten_View算子配置规则.md",
)
POLICY_PATH = (
    ".agents/task_records/"
    "20260727_config_only_correctness_first_parallel_mainline_policy.md"
)
EXPECTED_RULE_HASHES = {
    ".agents/rules/生成前必读索引.md": (
        "3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19"
    ),
    ".agents/rules/算子配置规则.md": (
        "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc"
    ),
    ".agents/rules/Flatten_View算子配置规则.md": (
        "28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee"
    ),
}
ACCEPTED_POLICY_HASHES = {
    "b73f528f76552baef3438acd3260498fb211ce359315a84fac776c715a0815a3",
    "b7ec52e4f57dad22b1dbbe8a556f15d3aa8ea49a7a559c3968622e23d03b7b54",
}


class FlattenPhysicalViewError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FlattenPhysicalViewError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise FlattenPhysicalViewError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _request(bundle: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == request_id
    ]
    if len(matches) != 1:
        raise FlattenPhysicalViewError(
            f"expected exactly one typed request {request_id}, got {len(matches)}"
        )
    return dict(matches[0])


def _single_port(request: Mapping[str, Any], direction: str) -> dict[str, Any]:
    ports = request.get("ports", {}).get(direction, [])
    runtime_ports = [
        item
        for item in ports
        if isinstance(item, Mapping) and item.get("kind") != "initializer"
    ]
    if len(runtime_ports) != 1:
        raise FlattenPhysicalViewError(
            f"{request.get('request_id')} must have one runtime {direction} port"
        )
    return dict(runtime_ports[0])


def _validate_typed_chain(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    producer = _request(bundle, REQUEST_IDS["producer"])
    view = _request(bundle, REQUEST_IDS["view"])
    consumer = _request(bundle, REQUEST_IDS["consumer"])
    if (
        producer.get("identity", {}).get("hw_op_type") != "DequantizeLinear"
        or view.get("identity", {}).get("hw_op_type") != "View"
        or consumer.get("identity", {}).get("hw_op_type") != "QuantizeLinear"
    ):
        raise FlattenPhysicalViewError("node0072/View/node0074 typed op chain differs")
    geometry = view.get("logical_geometry", {})
    if (
        geometry.get("attributes") != {"axis": 1}
        or geometry.get("input_shapes") != [list(INPUT_SHAPE)]
        or geometry.get("output_shapes") != [list(OUTPUT_SHAPE)]
        or geometry.get("input_dtypes") != ["float32"]
        or geometry.get("output_dtypes") != ["float32"]
    ):
        raise FlattenPhysicalViewError("node0073 typed View geometry differs")

    producer_out = _single_port(producer, "outputs")
    view_in = _single_port(view, "inputs")
    view_out = _single_port(view, "outputs")
    consumer_in = _single_port(consumer, "inputs")
    identity_fields = (
        "tensor_id",
        "onnx_name",
        "dtype",
        "shape",
        "identity_sha256",
        "identity_source",
    )
    if any(producer_out.get(key) != view_in.get(key) for key in identity_fields):
        raise FlattenPhysicalViewError("node0072 D and node0073 input identity differ")
    if any(view_out.get(key) != consumer_in.get(key) for key in identity_fields):
        raise FlattenPhysicalViewError("node0073 output and node0074 A identity differ")
    if (
        view_in.get("tensor_id") != TENSOR_IDS["input"]
        or view_out.get("tensor_id") != TENSOR_IDS["output"]
    ):
        raise FlattenPhysicalViewError("node0073 tensor IDs differ")
    return {"producer": producer, "view": view, "consumer": consumer}


def _load_golden(root: Path, tensor_id: str) -> np.ndarray:
    manifest = _load_object(root / GOLDEN_MANIFEST_PATH)
    descriptor = manifest.get("tensors", {}).get(tensor_id)
    if not isinstance(descriptor, Mapping):
        raise FlattenPhysicalViewError(f"golden tensor is missing: {tensor_id}")
    path = root / "artifacts/w3/golden_batch16" / str(descriptor.get("path"))
    if not path.is_file() or sha256_file(path) != descriptor.get("sha256"):
        raise FlattenPhysicalViewError(f"golden tensor identity differs: {tensor_id}")
    value = np.load(path, allow_pickle=False)
    if list(value.shape) != descriptor.get("shape") or str(value.dtype) != descriptor.get(
        "dtype"
    ):
        raise FlattenPhysicalViewError(f"golden tensor descriptor differs: {tensor_id}")
    return value


def _address_mapping_proof(base: int = 0, offset: int = 0) -> dict[str, Any]:
    digest = hashlib.sha256()
    first: dict[str, Any] | None = None
    last: dict[str, Any] | None = None
    for n in range(INPUT_SHAPE[0]):
        for c in range(INPUT_SHAPE[1]):
            input_offset = (
                n * INPUT_BYTE_STRIDES[0]
                + c * INPUT_BYTE_STRIDES[1]
            )
            output_offset = (
                n * OUTPUT_BYTE_STRIDES[0]
                + c * OUTPUT_BYTE_STRIDES[1]
            )
            if input_offset != output_offset:
                raise FlattenPhysicalViewError(
                    f"address offset differs at n={n}, c={c}"
                )
            record = {
                "input_index": [n, c, 0, 0],
                "output_index": [n, c],
                "byte_offset": input_offset,
                "address": base + offset + input_offset,
            }
            digest.update(canonical_json_bytes(record) + b"\n")
            if first is None:
                first = record
            last = record
    return {
        "formula": (
            "addr_in(n,c,0,0)=allocation_base+byte_offset+4*(n*2048+c)"
            "=addr_out(n,c)"
        ),
        "enumerated_element_count": ELEMENT_COUNT,
        "all_addresses_equal": True,
        "ordered_mapping_sha256": digest.hexdigest(),
        "first": first,
        "last": last,
    }


def _byte_coverage_proof(base: int = 0, offset: int = 0) -> dict[str, Any]:
    digest = hashlib.sha256()
    first = base + offset
    last = first + BYTE_COUNT - 1
    for address in range(first, last + 1):
        digest.update(f"{address}\n".encode("ascii"))
    return {
        "equation": (
            "required_byte_set={allocation_base+byte_offset+i | "
            "0<=i<131072}"
        ),
        "unique_byte_count": BYTE_COUNT,
        "first_address": first,
        "last_address": last,
        "ordered_byte_set_sha256": digest.hexdigest(),
    }


def _logical_and_materialized_projection() -> tuple[dict[str, Any], dict[str, Any]]:
    logical = {
        "op_kind": "View",
        "axis": 1,
        "input_tensor_id": TENSOR_IDS["input"],
        "output_tensor_id": TENSOR_IDS["output"],
        "dtype": "float32",
        "input_shape": list(INPUT_SHAPE),
        "output_shape": list(OUTPUT_SHAPE),
        "input_byte_strides": list(INPUT_BYTE_STRIDES),
        "output_byte_strides": list(OUTPUT_BYTE_STRIDES),
        "byte_span": BYTE_COUNT,
        "storage_id": None,
        "allocation_owner_request_id": None,
        "allocation_base": None,
        "producer_byte_offset": None,
        "consumer_byte_offset": None,
        "hardware_instruction_count": 0,
        "hardware_memory_request_count": 0,
    }
    materialized = {
        **logical,
        "storage_id": "node0072.D.storage_id",
        "allocation_owner_request_id": REQUEST_IDS["producer"],
        "allocation_base": "node0072.D.allocation_base",
        "producer_byte_offset": "node0072.D.byte_offset",
        "consumer_byte_offset": "node0074.A.byte_offset",
    }
    return logical, materialized


def _materialized_leaf_diff() -> list[dict[str, Any]]:
    return [
        {
            "path": "$.storage_id",
            "field_class": "non_base",
            "owner": "activation_allocator",
            "input_source": "node0072 D addressed allocation",
            "formula": (
                "node0073.input.storage_id=node0073.output.storage_id="
                "node0072.D.storage_id=node0074.A.storage_id"
            ),
            "old_value": None,
            "expected_new_value": "node0072.D.storage_id",
            "authorization": "typed View zero-copy storage identity",
        },
        {
            "path": "$.allocation_owner_request_id",
            "field_class": "non_base",
            "owner": "activation_allocator",
            "input_source": "typed producer request identity",
            "formula": "owner=request_id(node0072 D producer)",
            "old_value": None,
            "expected_new_value": REQUEST_IDS["producer"],
            "authorization": "View borrows and never reallocates or releases storage",
        },
        {
            "path": "$.allocation_base",
            "field_class": "base",
            "owner": "planner_address_binder",
            "input_source": "node0072 D addressed execplan",
            "formula": "view_base=node0072.D.allocation_base=node0074.A.allocation_base",
            "old_value": None,
            "expected_new_value": "node0072.D.allocation_base",
            "authorization": "planner-owned physical base binding",
        },
        {
            "path": "$.producer_byte_offset",
            "field_class": "base_offset",
            "owner": "planner_address_binder",
            "input_source": "node0072 D addressed execplan",
            "formula": "view_input_offset=node0072.D.byte_offset",
            "old_value": None,
            "expected_new_value": "node0072.D.byte_offset",
            "authorization": "planner-owned producer offset binding",
        },
        {
            "path": "$.consumer_byte_offset",
            "field_class": "base_offset",
            "owner": "planner_address_binder",
            "input_source": "node0074 A addressed execplan",
            "formula": "view_output_offset=node0074.A.byte_offset=node0072.D.byte_offset",
            "old_value": None,
            "expected_new_value": "node0074.A.byte_offset",
            "authorization": "planner-owned consumer offset binding",
        },
    ]


def _source_receipt(root: Path) -> list[dict[str, Any]]:
    paths = (
        ".agents/agent.md",
        ".agents/plan.md",
        *RULE_PATHS,
        POLICY_PATH,
        LOWERING_PATH,
        LIFETIME_PATH,
        GOLDEN_MANIFEST_PATH,
        "resnet50_pipeline/lowering/registry.py",
        "resnet50_pipeline/lowering/legacy_plan.py",
        "resnet50_pipeline/stage_state_lifetime_contract.py",
    )
    receipt = []
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise FlattenPhysicalViewError(f"required source is missing: {relative}")
        observed = sha256_file(path)
        expected = EXPECTED_RULE_HASHES.get(relative)
        if expected is not None and observed != expected:
            raise FlattenPhysicalViewError(
                f"frozen rule/policy identity differs: {relative}"
            )
        if relative == POLICY_PATH and observed not in ACCEPTED_POLICY_HASHES:
            raise FlattenPhysicalViewError(
                "mainline config-only policy identity differs"
            )
        receipt.append(
            {
                "path": relative,
                "sha256": observed,
                "semantic_gate": relative in EXPECTED_RULE_HASHES,
                "mutable_provenance": relative == ".agents/plan.md",
                "accepted_lineage_append": (
                    relative == POLICY_PATH
                    and observed
                    == "b7ec52e4f57dad22b1dbbe8a556f15d3aa8ea49a7a559c3968622e23d03b7b54"
                ),
            }
        )
    return receipt


def build_view_metadata(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    bundle = _load_object(root / LOWERING_PATH)
    requests = _validate_typed_chain(bundle)
    lifetime = _load_object(root / LIFETIME_PATH)
    view_proof = lifetime.get("view", {})
    if (
        view_proof.get("request_id") != REQUEST_IDS["view"]
        or view_proof.get("exact_byte_equal") is not True
        or view_proof.get("logical_zero_copy_proven") is not True
        or view_proof.get("physical_zero_copy_proven") is not False
    ):
        raise FlattenPhysicalViewError("upstream logical View proof differs")

    golden_input = _load_golden(root, TENSOR_IDS["input"])
    golden_output = _load_golden(root, TENSOR_IDS["output"])
    input_bytes = np.ascontiguousarray(golden_input).tobytes()
    output_bytes = np.ascontiguousarray(golden_output).tobytes()
    if (
        golden_input.shape != INPUT_SHAPE
        or golden_output.shape != OUTPUT_SHAPE
        or golden_input.dtype != np.dtype("float32")
        or golden_output.dtype != np.dtype("float32")
        or not golden_input.flags.c_contiguous
        or not golden_output.flags.c_contiguous
        or input_bytes != output_bytes
        or not np.array_equal(golden_input.reshape(OUTPUT_SHAPE), golden_output)
    ):
        raise FlattenPhysicalViewError("frozen node0073 golden is not an exact C-order view")

    proof = _address_mapping_proof()
    logical_projection, materialized_projection = (
        _logical_and_materialized_projection()
    )
    relative_coverage = _byte_coverage_proof()
    metadata: dict[str, Any] = {
        "schema": SCHEMA,
        "test_id": TEST_ID,
        "identity": {
            "request_id": REQUEST_IDS["view"],
            "request_sha256": requests["view"]["request_sha256"],
            "node_id": "node-0073",
            "onnx_name": "flatten_473",
            "onnx_op_type": "Flatten",
            "hw_op_type": "View",
            "axis": 1,
        },
        "logical_tensors": {
            "input": {
                "tensor_id": TENSOR_IDS["input"],
                "producer_request_id": REQUEST_IDS["producer"],
                "shape": list(INPUT_SHAPE),
                "dtype": "float32",
                "order": "C",
                "byte_strides": list(INPUT_BYTE_STRIDES),
                "identity_sha256": _single_port(
                    requests["view"], "inputs"
                )["identity_sha256"],
            },
            "output": {
                "tensor_id": TENSOR_IDS["output"],
                "consumer_request_id": REQUEST_IDS["consumer"],
                "shape": list(OUTPUT_SHAPE),
                "dtype": "float32",
                "order": "C",
                "byte_strides": list(OUTPUT_BYTE_STRIDES),
                "identity_sha256": _single_port(
                    requests["view"], "outputs"
                )["identity_sha256"],
            },
            "element_count": ELEMENT_COUNT,
            "byte_count": BYTE_COUNT,
            "logical_tensor_ids_distinct": True,
            "physical_storage_identity_required": True,
        },
        "materialization": {
            "kind": "execplan_metadata_zero_copy_alias",
            "emit_arithmetic_json": False,
            "emit_mapping_or_bitstream": False,
            "hardware_config_count": 0,
            "hardware_instruction_count": 0,
            "hardware_memory_request_count": 0,
            "execplan_directive": {
                "kind": "BindTensorViewAlias",
                "input_tensor_id": TENSOR_IDS["input"],
                "output_tensor_id": TENSOR_IDS["output"],
                "allocation_owner_request_id": REQUEST_IDS["producer"],
                "base_selector": "node0072.D.allocation_base",
                "input_byte_offset_selector": "node0072.D.byte_offset",
                "output_byte_offset_expression": "node0072.D.byte_offset",
                "consumer_base_selector": "node0074.A.allocation_base",
                "consumer_byte_offset_selector": "node0074.A.byte_offset",
            },
            "required_equalities": [
                "node0072.D.storage_id == node0073.input.storage_id",
                "node0073.input.storage_id == node0073.output.storage_id",
                "node0073.output.storage_id == node0074.A.storage_id",
                "node0072.D.allocation_base == node0074.A.allocation_base",
                "node0072.D.byte_offset == node0074.A.byte_offset",
                "node0072.D.byte_span == node0074.A.byte_span == 131072",
            ],
        },
        "materialized_nonbase_field_ownership": {
            "rule_id": "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "logical_projection": logical_projection,
            "logical_projection_sha256": sha256_bytes(
                canonical_json_bytes(logical_projection)
            ),
            "final_materialized_projection": materialized_projection,
            "final_materialized_projection_sha256": sha256_bytes(
                canonical_json_bytes(materialized_projection)
            ),
            "leaf_diff": _materialized_leaf_diff(),
            "changed_leaf_count": 5,
            "nonbase_changed_leaf_count": 2,
            "undeclared_changed_leaf_count": 0,
            "nonbase_fields_not_listed_are_immutable": True,
            "endpoint_address_resolution_pending": True,
        },
        "allocation_ownership": {
            "owner": "activation_allocator_for_node0072_D",
            "view_owns_allocation": False,
            "node0074_access": "read-only borrower",
            "alias_may_allocate": False,
            "alias_may_release": False,
        },
        "accepted_handshake_lifetime": {
            "event_order": list(ACCEPTED_EVENT_ORDER),
            "visibility_point": "node0072.completion_accepted",
            "consumer_acquire_point": "node0074.first_input_data_accepted",
            "release_point": "allocation.release_accepted",
            "release_precondition": (
                "node0074.final_input_data_accepted and no pending/replayed "
                "node0074 input transactions"
            ),
            "conservative_fallback": (
                "if final-input-data acceptance is not observable, retain through "
                "node0074.completion_accepted; this changes lifetime only, not data"
            ),
        },
        "address_mapping_proof": proof,
        "formal_output_byte_coverage": {
            "view_owned_write_byte_count": 0,
            "coverage_kind": "inherited_node0072_D_written_byte_set",
            "required_relative_byte_set": relative_coverage,
            "required_unique_output_bytes": BYTE_COUNT,
            "producer_materialized_occurrence_coverage_proven": False,
            "consumer_materialized_read_coverage_proven": False,
            "reason": (
                "View emits no write; target coverage must be recalculated from "
                "node0072 final write and node0074 final read occurrence/address "
                "equations in the endpoint binding certificate"
            ),
        },
        "input_replay_policy": {
            "rule_id": "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "input_or_constant_replay_enabled": False,
            "copy_enabled": False,
            "host_precomputed_internal_tensor_enabled": False,
            "host_precomputed_scaled_tensor_enabled": False,
            "host_precomputed_rounded_tensor_enabled": False,
            "host_precomputed_saturated_tensor_enabled": False,
            "host_precomputed_final_tensor_enabled": False,
            "allowed_data_source": (
                "only the final node0072 D producer output through physical alias"
            ),
            "calculation_owner_unchanged": True,
            "forbidden_boundary_crossing": (
                "host may not calculate any node0072, node0073 or node0074 "
                "internal/scaled/rounded/saturated/final tensor"
            ),
        },
        "golden_proof": {
            "input_path": (
                "artifacts/w3/golden_batch16/tensors/"
                "tensor-50c285690f899b1b.npy"
            ),
            "output_path": (
                "artifacts/w3/golden_batch16/tensors/"
                "tensor-9b1363d3baf474c8.npy"
            ),
            "byte_count": len(input_bytes),
            "exact_bytes_equal": True,
            "bytes_sha256": sha256_bytes(input_bytes),
            "reshape_elementwise_equal": True,
        },
        "binding_certificate_interface": {
            "schema": BINDING_SCHEMA,
            "required_source_bindings": list(SOURCE_BINDING_KEYS),
            "required_fields": [
                "storage_id",
                "allocation_owner_request_id",
                "allocation_base",
                "producer_byte_offset",
                "consumer_byte_offset",
                "byte_span",
                "producer_byte_strides",
                "consumer_byte_strides",
                "event_sequence",
                "no_pending_or_replayed_consumer_reads_at_release",
                "producer_final_output_coverage",
                "consumer_final_input_coverage",
            ],
        },
        "dependencies": {
            "node0072": {
                "request_id": REQUEST_IDS["producer"],
                "port": "D",
                "must_supply": [
                    "storage_id/allocation owner",
                    "addressed allocation_base+byte_offset",
                    "C-order physical byte strides [8192,4,4,4]",
                    "131072-byte visible span",
                    "final output write accepted and completion accepted events",
                    "final occurrence/address unique written-byte coverage",
                    "addressed execplan and layout contract hashes",
                ],
            },
            "node0074": {
                "request_id": REQUEST_IDS["consumer"],
                "port": "A",
                "must_supply": [
                    "same storage_id/allocation_base+byte_offset",
                    "C-order physical byte strides [8192,4]",
                    "131072-byte read span",
                    "first/final input data accepted and no-replay release proof",
                    "final occurrence/address unique read-byte coverage",
                    "addressed execplan and layout contract hashes",
                ],
            },
        },
        "bypass_annotation": {
            "bypass_reason": (
                "Flatten is an ONNX physical view; emitting a computational operator "
                "would add non-semantic work and functional RTL changes are frozen."
            ),
            "contradicted_or_missing_native_path": (
                "the legacy execplan intentionally excludes Flatten and the native "
                "operator JSON/mapper path has no View computation to encode"
            ),
            "exact_equivalence_scope": (
                "frozen node0073 axis=1 float32 C-contiguous "
                "[16,2048,1,1] to [16,2048] instance"
            ),
            "materialized_configuration_mechanism": (
                "planner/execplan metadata alias with one storage identity, identical "
                "base+offset, zero View instruction and zero View memory request"
            ),
            "performance_and_resource_cost": (
                "zero copy traffic and zero View compute; producer allocation remains "
                "live through node0074 final accepted input data, increasing live-range "
                "pressure and potentially constraining scheduling"
            ),
            "unresolved_production_blocker": (
                "node0072 D and node0074 A final addressed layout/execplan plus accepted-"
                "handshake lifetime certificate are not yet materialized"
            ),
            "claim_boundary": (
                "eligible only for CONFIG_ONLY_CORRECTNESS_BASELINE after a validated "
                "endpoint binding certificate; no production/performance/E4/E5 claim"
            ),
        },
        "release": {
            "status": "ENDPOINT_BINDING_PENDING",
            "claim_label": None,
            "eligible_claim_label_after_binding": (
                "CONFIG_ONLY_CORRECTNESS_BASELINE"
            ),
            "claim_enabled": False,
            "independent_target_local_e2": False,
            "formal_target_instance_allowed": False,
            "server_package": False,
            "rtl_modified": False,
            "open_blockers": [
                "B_VIEW_PRODUCER_ALLOCATION",
                "B_VIEW_CONSUMER_ALLOCATION",
                "B_VIEW_BYTE_OFFSET_IDENTITY",
                "B_VIEW_BUFFER_LIFETIME",
            ],
        },
        "rule_ids": [
            "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-VIEW-METADATA-ONLY-001",
            "CDA-VIEW-PHYSICAL-IDENTITY-001",
            "CDA-VIEW-ENDPOINT-COVERAGE-001",
            "CDA-VIEW-ACCEPTED-LIFETIME-001",
            "CDA-VIEW-INTEGRATED-CLAIM-BOUNDARY-001",
        ],
        "read_receipt": _source_receipt(root),
        "omitted_files": [
            {
                "path": ".agents/rules/NDP硬件字段语义.md",
                "reason": (
                    "View emits no LC/MSE/Buffer/SA/GA/N2N field and no hardware "
                    "configuration"
                ),
            },
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "no server package is generated or authorized",
            },
        ],
    }
    metadata["metadata_sha256"] = sha256_bytes(canonical_json_bytes(metadata))
    return metadata


def _parse_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise FlattenPhysicalViewError(f"{field} must be a nonnegative integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as error:
            raise FlattenPhysicalViewError(f"{field} is not an integer") from error
    else:
        raise FlattenPhysicalViewError(f"{field} must be a nonnegative integer")
    if result < 0:
        raise FlattenPhysicalViewError(f"{field} must be nonnegative")
    return result


def validate_binding_certificate(
    metadata: Mapping[str, Any],
    certificate: Mapping[str, Any],
    source_root: Path,
) -> dict[str, Any]:
    if certificate.get("schema") != BINDING_SCHEMA:
        raise FlattenPhysicalViewError("binding certificate schema differs")
    if certificate.get("storage_id") in (None, ""):
        raise FlattenPhysicalViewError("binding storage_id is missing")
    if (
        certificate.get("allocation_owner_request_id")
        != REQUEST_IDS["producer"]
    ):
        raise FlattenPhysicalViewError("allocation owner must remain node0072 D")
    base = _parse_nonnegative_int(certificate.get("allocation_base"), "allocation_base")
    producer_offset = _parse_nonnegative_int(
        certificate.get("producer_byte_offset"), "producer_byte_offset"
    )
    consumer_offset = _parse_nonnegative_int(
        certificate.get("consumer_byte_offset"), "consumer_byte_offset"
    )
    if producer_offset != consumer_offset:
        raise FlattenPhysicalViewError("producer/consumer byte offsets differ")
    if certificate.get("byte_span") != BYTE_COUNT:
        raise FlattenPhysicalViewError("binding byte span differs")
    if certificate.get("producer_byte_strides") != list(INPUT_BYTE_STRIDES):
        raise FlattenPhysicalViewError("producer byte strides differ")
    if certificate.get("consumer_byte_strides") != list(OUTPUT_BYTE_STRIDES):
        raise FlattenPhysicalViewError("consumer byte strides differ")
    if certificate.get("order") != "C" or certificate.get("dtype") != "float32":
        raise FlattenPhysicalViewError("binding order/dtype differs")
    event_sequence = certificate.get("event_sequence")
    if not isinstance(event_sequence, Mapping):
        raise FlattenPhysicalViewError("binding event_sequence is missing")
    sequences = []
    for event in ACCEPTED_EVENT_ORDER:
        sequences.append(_parse_nonnegative_int(event_sequence.get(event), event))
    if any(left >= right for left, right in zip(sequences, sequences[1:])):
        raise FlattenPhysicalViewError("accepted handshake event order is not strict")
    if certificate.get("no_pending_or_replayed_consumer_reads_at_release") is not True:
        raise FlattenPhysicalViewError("release still has pending/replayed consumer reads")
    absolute_coverage = _byte_coverage_proof(base, producer_offset)
    if certificate.get("producer_final_output_coverage") != absolute_coverage:
        raise FlattenPhysicalViewError(
            "producer final occurrence/address byte coverage differs"
        )
    if certificate.get("consumer_final_input_coverage") != absolute_coverage:
        raise FlattenPhysicalViewError(
            "consumer final occurrence/address byte coverage differs"
        )

    sources = certificate.get("sources")
    if not isinstance(sources, Mapping):
        raise FlattenPhysicalViewError("binding source identities are missing")
    source_identities: dict[str, Any] = {}
    root = source_root.resolve()
    for key in SOURCE_BINDING_KEYS:
        binding = sources.get(key)
        if not isinstance(binding, Mapping):
            raise FlattenPhysicalViewError(f"binding source is missing: {key}")
        relative = binding.get("path")
        expected_sha = binding.get("sha256")
        if not isinstance(relative, str) or not SHA256_RE.fullmatch(
            str(expected_sha)
        ):
            raise FlattenPhysicalViewError(f"invalid binding source identity: {key}")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FlattenPhysicalViewError(f"binding source path is invalid: {key}")
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise FlattenPhysicalViewError(f"binding source hash differs: {key}")
        source_identities[key] = {
            "path": relative,
            "sha256": observed_sha,
            "size_bytes": path.stat().st_size,
        }

    proof = _address_mapping_proof(base, producer_offset)
    result = {
        "valid": True,
        "storage_id": certificate["storage_id"],
        "allocation_owner_request_id": REQUEST_IDS["producer"],
        "allocation_base": f"0x{base:X}",
        "byte_offset": producer_offset,
        "byte_span": BYTE_COUNT,
        "address_mapping_proof": proof,
        "formal_output_byte_coverage": absolute_coverage,
        "producer_written_byte_coverage_complete": True,
        "consumer_read_byte_coverage_complete": True,
        "accepted_handshake_lifetime_proven": True,
        "release_after_final_consumer_input_data_accepted": True,
        "source_identities": source_identities,
    }
    result["binding_proof_sha256"] = sha256_bytes(canonical_json_bytes(result))
    return result


def validate_view_metadata(
    metadata: Mapping[str, Any],
    project_root: Path,
    certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    expected = build_view_metadata(project_root)
    if metadata != expected:
        raise FlattenPhysicalViewError(
            "View metadata differs from deterministic typed-request derivation"
        )
    binding = (
        validate_binding_certificate(metadata, certificate, project_root)
        if certificate is not None
        else None
    )
    integrated = binding is not None
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "test_id": TEST_ID,
        "valid": True,
        "metadata_sha256": metadata["metadata_sha256"],
        "typed_request_chain_exact": True,
        "golden_exact_byte_equal": True,
        "logical_address_mapping_complete": True,
        "enumerated_element_count": ELEMENT_COUNT,
        "materialized_leaf_diff_checked": True,
        "undeclared_nonbase_changed_leaf_count": 0,
        "formal_output_byte_coverage_complete": integrated,
        "view_hardware_instruction_count": 0,
        "view_hardware_memory_request_count": 0,
        "target_binding_certificate_present": integrated,
        "integrated_target_local_e2": integrated,
        "independent_target_local_e2": False,
        "status": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE"
            if integrated
            else "ENDPOINT_BINDING_PENDING"
        ),
        "claim_label": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE" if integrated else None
        ),
        "eligible_claim_label_after_binding": (
            None if integrated else "CONFIG_ONLY_CORRECTNESS_BASELINE"
        ),
        "claim_enabled": integrated,
        "input_replay_enabled": False,
        "host_precomputed_internal_tensor_used": False,
        "binding_proof": binding,
        "open_blockers": (
            []
            if integrated
            else list(metadata["release"]["open_blockers"])
        ),
        "claim_boundary": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE; target physical binding, local E2 "
            "and no-copy lifetime proven; production/performance/E4/E5 not claimed"
            if integrated
            else (
                "contract and logical/address-offset proof complete; exact target "
                "node0072/node0074 binding is required before "
                "CONFIG_ONLY_CORRECTNESS_BASELINE is enabled"
            )
        ),
    }
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report


def build_contract(
    project_root: Path,
    config_path: Path,
    report_path: Path,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    root = project_root.resolve()
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "test_id": TEST_ID,
        "status": (
            "ENDPOINT_BINDING_PENDING"
            if report.get("integrated_target_local_e2") is not True
            else "TARGET_LOCAL_E2_COMPLETE"
        ),
        "claim_label": report.get("claim_label"),
        "eligible_claim_label_after_binding": report.get(
            "eligible_claim_label_after_binding"
        ),
        "claim_enabled": report.get("claim_enabled") is True,
        "machine_config": {
            "path": config_path.resolve().relative_to(root).as_posix(),
            "sha256": sha256_file(config_path),
            "kind": "execplan_metadata_zero_copy_alias",
            "arithmetic_json": False,
        },
        "validator_report": {
            "path": report_path.resolve().relative_to(root).as_posix(),
            "sha256": sha256_file(report_path),
        },
        "closed": [
            "typed producer/View/consumer tensor identity",
            "axis=1 shape/order/stride identity",
            "32768-of-32768 element address-offset mapping",
            "static/logical to materialized metadata leaf diff ownership",
            "zero View instruction/request materialization",
            "allocation ownership and accepted-handshake release contract",
        ],
        "open": list(report.get("open_blockers", [])),
        "local_e2": {
            "independent": False,
            "integrated_target": report.get("integrated_target_local_e2") is True,
            "reason": (
                "View owns no allocation; target local E2 necessarily consumes "
                "node0072 D and node0074 A addressed bindings"
            ),
        },
        "package_release": {
            "state": "NOT_BUILT",
            "server_package": False,
            "rtl_entries": 0,
            "reason": "local metadata/contract task; no server authorization or lease",
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def build_artifact_manifest(
    project_root: Path,
    config_path: Path,
    report_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    files = []
    for path in (config_path, report_path, contract_path):
        files.append(
            {
                "path": path.resolve().relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest: dict[str, Any] = {
        "schema": "resnet50-flatten-physical-view-artifact-manifest-v1",
        "test_id": TEST_ID,
        "status": "ENDPOINT_BINDING_PENDING",
        "claim_label": None,
        "eligible_claim_label_after_binding": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE"
        ),
        "claim_enabled": False,
        "integrated_target_local_e2": False,
        "server_package": False,
        "files": files,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    return manifest


def build_node0073_view_assets(
    project_root: Path,
    *,
    config_path: Path | None = None,
    artifact_root: Path | None = None,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    config = (
        config_path
        if config_path is not None
        else root / "configs/view/node0073_zero_copy_view_v1.json"
    )
    artifact = (
        artifact_root
        if artifact_root is not None
        else root
        / "artifacts/operator_config_validation/r5-flatten-node0073-view-v1"
    )
    contract = (
        contract_path
        if contract_path is not None
        else root
        / "contracts/operator_config/flatten_node0073_physical_view_v1.json"
    )
    report_path = artifact / "validation_report.json"
    manifest_path = artifact / "manifest.json"

    metadata = build_view_metadata(root)
    _write_json(config, metadata)
    report = validate_view_metadata(metadata, root)
    _write_json(report_path, report)
    contract_value = build_contract(root, config, report_path, report)
    _write_json(contract, contract_value)
    manifest = build_artifact_manifest(root, config, report_path, contract)
    _write_json(manifest_path, manifest)
    return {
        "test_id": TEST_ID,
        "config_path": config.relative_to(root).as_posix(),
        "config_sha256": sha256_file(config),
        "contract_path": contract.relative_to(root).as_posix(),
        "contract_sha256": sha256_file(contract),
        "artifact_manifest_path": manifest_path.relative_to(root).as_posix(),
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "integrated_target_local_e2": False,
        "status": "ENDPOINT_BINDING_PENDING",
        "claim_label": None,
        "eligible_claim_label_after_binding": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE"
        ),
        "claim_enabled": False,
        "server_package": False,
    }


__all__ = [
    "ACCEPTED_EVENT_ORDER",
    "BINDING_SCHEMA",
    "BYTE_COUNT",
    "ELEMENT_COUNT",
    "FlattenPhysicalViewError",
    "INPUT_BYTE_STRIDES",
    "OUTPUT_BYTE_STRIDES",
    "SOURCE_BINDING_KEYS",
    "build_node0073_view_assets",
    "build_view_metadata",
    "validate_binding_certificate",
    "validate_view_metadata",
]
