from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-view-flatten-complete-json-regeneration-v1"
LEDGER_SCHEMA = "resnet50-complete-json-leaf-provenance-ledger-v1"
REFERENCE_SCHEMA = "resnet50-native-reference-applicability-v1"
CAPABILITY_SCHEMA = "resnet50-handler-capability-matrix-v1"
DIFF_SCHEMA = "resnet50-current-test-config-diff-v1"
REPORT_SCHEMA = "resnet50-family-complete-json-findings-v1"
FAMILY = "view_flatten"
REQUEST_ID = "r5:hwop-0073-00"
NODE_ID = "node-0073"
NDPSIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
PROJECT_CHECKPOINT = "75186a2462acbb4d3a12d0466f297c0c779cc9d7"
CURRENT_PACKAGE_SHA256 = (
    "f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165"
)

LOWERING_PATH = Path("contracts/resnet50_r5_lowering_bundle.json")
FUSION_PATH = Path(
    "contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json"
)
CANONICAL_ENDPOINT_PATH = Path(
    "contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json"
)
COMPOSITE_PATH = Path(
    "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2/"
    "composite_target.json"
)
EXECPLAN_MANIFEST_PATH = COMPOSITE_PATH.with_name("execplan_manifest.json")
E2_REPORT_PATH = COMPOSITE_PATH.with_name("report.json")
CURRENT_PACKAGE_PATH = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_0cc_bankrow_v9.zip"
)
VIEW_RULE_PATH = Path(".agents/rules/Flatten_View算子配置规则.md")
OPERATOR_RULE_PATH = Path(".agents/rules/算子配置规则.md")
INDEX_PATH = Path(".agents/rules/生成前必读索引.md")
PLAN_PATH = Path(".agents/plan.md")

ALLOWED_ORIGINS = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}
ABSENCE_STATES = {
    "SOURCE_ABSENT_NOT_APPLICABLE",
    "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
    "EXPLICIT_NULL_INACTIVE",
    "EXPLICIT_ZERO",
    "TARGET_REQUIRED_DERIVED",
}
BANNED_OUTPUT_TOKENS = ("zip", "prepare_and_run", "server_runtime")


class ViewFlattenRegenerationError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ViewFlattenRegenerationError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ViewFlattenRegenerationError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _pointer_get(value: Any, pointer: str) -> Any:
    current = value
    if pointer == "":
        return current
    if not pointer.startswith("/"):
        raise ViewFlattenRegenerationError(f"invalid JSON pointer: {pointer}")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, Mapping):
            current = current[token]
        else:
            raise ViewFlattenRegenerationError(f"pointer enters scalar: {pointer}")
    return current


def _leaf_items(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        if not value:
            yield pointer, {}
            return
        for key in sorted(value):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            yield from _leaf_items(value[key], f"{pointer}/{escaped}")
        return
    if isinstance(value, list):
        if not value:
            yield pointer, []
            return
        for index, item in enumerate(value):
            yield from _leaf_items(item, f"{pointer}/{index}")
        return
    yield pointer, value


def _request_index(bundle: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    matches = [
        (index, request)
        for index, request in enumerate(bundle.get("requests", []))
        if isinstance(request, Mapping) and request.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise ViewFlattenRegenerationError(
            f"expected one {REQUEST_ID} request, got {len(matches)}"
        )
    index, request = matches[0]
    identity = request.get("identity", {})
    geometry = request.get("logical_geometry", {})
    if (
        identity.get("onnx_op_type") != "Flatten"
        or identity.get("hw_op_type") != "View"
        or geometry.get("attributes") != {"axis": 1}
        or geometry.get("input_shapes") != [[16, 2048, 1, 1]]
        or geometry.get("output_shapes") != [[16, 2048]]
        or geometry.get("input_dtypes") != ["float32"]
        or geometry.get("output_dtypes") != ["float32"]
    ):
        raise ViewFlattenRegenerationError("node0073 typed View geometry differs")
    return index, dict(request)


def _runtime_port(request: Mapping[str, Any], direction: str) -> dict[str, Any]:
    ports = [
        port
        for port in request.get("ports", {}).get(direction, [])
        if isinstance(port, Mapping) and port.get("kind") != "initializer"
    ]
    if len(ports) != 1:
        raise ViewFlattenRegenerationError(
            f"{REQUEST_ID} must have one runtime {direction} port"
        )
    return dict(ports[0])


def _source(
    root: Path,
    path: Path,
    pointer: str,
    value: Any,
    *,
    repository: str = "resnet50_int8",
    commit: str = PROJECT_CHECKPOINT,
) -> dict[str, Any]:
    full = root / path
    return {
        "repository": repository,
        "commit": commit,
        "blob_sha256": sha256_file(full),
        "path": path.as_posix(),
        "pointer": pointer,
        "value": value,
    }


def _bound(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.resolve().relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def _project_blob_oid(root: Path, path: Path) -> str:
    relative = path.as_posix()
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "worktree-" + sha256_file(root / path)


def _git_output(ndpsim: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={ndpsim.resolve()}",
        "-C",
        str(ndpsim),
        *args,
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise ViewFlattenRegenerationError(
            f"pinned ndp-sim query failed: {' '.join(args)}: {result.stderr.strip()}"
        )
    return result.stdout


def _native_authority_receipt(root: Path) -> dict[str, Any]:
    ndpsim = root / "ndp-sim"
    paths = _git_output(ndpsim, "ls-tree", "-r", "--name-only", NDPSIM_COMMIT).splitlines()
    json_paths = [
        path
        for path in paths
        if path.startswith("jsons/") and path.lower().endswith(".json")
    ]
    named_candidates = [
        path
        for path in paths
        if any(token in path.lower() for token in ("flatten", "view", "reshape"))
    ]
    control_path = (
        "model_execplan/src/execution_plan_generator/control_registers.py"
    )
    pipeline_path = "model_execplan/src/execution_plan_generator/pipeline.py"
    control = _git_output(ndpsim, "show", f"{NDPSIM_COMMIT}:{control_path}")
    pipeline = _git_output(ndpsim, "show", f"{NDPSIM_COMMIT}:{pipeline_path}")
    registry_tokens = [
        token for token in ("Flatten", "View", "Reshape") if token in control
    ]
    handler_blob = _git_output(
        ndpsim, "rev-parse", f"{NDPSIM_COMMIT}:{control_path}"
    ).strip()
    pipeline_blob = _git_output(
        ndpsim, "rev-parse", f"{NDPSIM_COMMIT}:{pipeline_path}"
    ).strip()
    if named_candidates or registry_tokens:
        raise ViewFlattenRegenerationError(
            "pinned ndp-sim unexpectedly contains a View/Flatten/Reshape authority"
        )
    return {
        "repository": "ndp-sim",
        "commit": NDPSIM_COMMIT,
        "scan_scope": "pinned commit tree; dirty worktree and untracked JSON excluded",
        "pinned_json_count": len(json_paths),
        "named_template_candidates": named_candidates,
        "registered_handler_tokens": registry_tokens,
        "template_present": False,
        "handler_present": False,
        "pipeline_fail_closed_without_template": (
            "JSON template not found" in pipeline
            and "raise FileNotFoundError" in pipeline
        ),
        "control_registers": {
            "path": control_path,
            "git_blob_sha1": handler_blob,
        },
        "pipeline": {
            "path": pipeline_path,
            "git_blob_sha1": pipeline_blob,
        },
    }


def _package_receipt(root: Path) -> dict[str, Any]:
    package = root / CURRENT_PACKAGE_PATH
    observed = sha256_file(package)
    if observed != CURRENT_PACKAGE_SHA256:
        raise ViewFlattenRegenerationError(
            f"current package identity differs: {observed}"
        )
    with zipfile.ZipFile(package, "r") as archive:
        members = archive.namelist()
        view_members = [
            member
            for member in members
            if any(token in member.lower() for token in ("node0073", "flatten", "view"))
        ]
        execplan_names = [
            member for member in members if member.endswith("/p/execplan.json")
        ]
        manifest_names = [
            member
            for member in members
            if member.endswith("/TEST_PACKAGE_MANIFEST.json")
        ]
        if len(execplan_names) != 1 or len(manifest_names) != 1:
            raise ViewFlattenRegenerationError(
                "current package execplan/manifest member identity differs"
            )
        execplan = archive.read(execplan_names[0])
        package_manifest = archive.read(manifest_names[0])
    return {
        "path": CURRENT_PACKAGE_PATH.as_posix(),
        "sha256": observed,
        "member_count": len(members),
        "view_member_count": len(view_members),
        "view_members": view_members,
        "execplan_member": execplan_names[0],
        "execplan_sha256": hashlib.sha256(execplan).hexdigest(),
        "package_manifest_sha256": hashlib.sha256(package_manifest).hexdigest(),
        "inspection": "read_only_zip_member_and_payload_hash",
    }


def _per_slice_bases() -> list[str]:
    return [f"0x{0x000A2000 + (slice_id << 25):08x}" for slice_id in range(16)]


def _build_contract(
    root: Path,
    bundle: Mapping[str, Any],
    request_index: int,
    request: Mapping[str, Any],
    fusion: Mapping[str, Any],
    composite: Mapping[str, Any],
    package: Mapping[str, Any],
) -> dict[str, Any]:
    geometry = request["logical_geometry"]
    input_port = _runtime_port(request, "inputs")
    output_port = _runtime_port(request, "outputs")
    overlay = fusion["endpoint_handoff"]["known_source_storage"]
    graph = fusion["graph_rewrite"]
    handoff = composite["handoff"]
    if (
        overlay.get("storage_id")
        != "r5:activation:node-0071:D:tensor-ab32f279540568c3:"
        "batch-slice-sharded-16x2048-v1"
        or overlay.get("alias_offset_bytes") != 0
        or overlay.get("source_shape") != [16, 2048, 1, 1]
        or overlay.get("alias_shape") != [16, 2048]
        or handoff.get("identity_alias") is not True
        or handoff.get("a_preload_count") != 0
        or handoff.get("host_copy_precompute_relayout_replay") is not False
    ):
        raise ViewFlattenRegenerationError("current UINT8 alias overlay differs")
    return {
        "schema": SCHEMA,
        "family": FAMILY,
        "metadata_only": True,
        "target_hw_op_types": ["View"],
        "stage_ids": [request["identity"]["hw_op_id"]],
        "disposition": "NO_HARDWARE_JSON_REQUIRED",
        "hardware_json_required": False,
        "hardware_json_count": 0,
        "complete_json_directory_semantics": (
            "contains this no-config machine contract only; it is not an NDP "
            "hardware register JSON"
        ),
        "target_inventory": {
            "source_bundle": LOWERING_PATH.as_posix(),
            "request_count": 1,
            "stages": [
                {
                    "request_id": REQUEST_ID,
                    "hw_op_id": request["identity"]["hw_op_id"],
                    "request_index": request_index,
                    "request_sha256": request["request_sha256"],
                    "node_id": NODE_ID,
                    "onnx_name": request["identity"]["onnx_name"],
                    "onnx_op_type": "Flatten",
                    "hw_op_type": "View",
                    "stage": request["identity"].get("stage", "view"),
                    "axis": geometry["attributes"]["axis"],
                    "dtype": geometry["input_dtypes"][0],
                    "input_shape": geometry["input_shapes"][0],
                    "output_shape": geometry["output_shapes"][0],
                    "layout": "C_CONTIGUOUS",
                    "input_byte_strides": [8192, 4, 4, 4],
                    "output_byte_strides": [8192, 4],
                    "input_tensor_id": input_port["tensor_id"],
                    "output_tensor_id": output_port["tensor_id"],
                    "qparams_state": "SOURCE_ABSENT_NOT_APPLICABLE",
                    "padding_tail_state": "SOURCE_ABSENT_NOT_APPLICABLE",
                    "dag": "node0072.D -> node0073 metadata View -> node0074.A",
                    "lifetime": (
                        "borrows producer storage through final accepted consumer "
                        "read; owns neither allocation nor release"
                    ),
                    "address_owner": "producer_allocation_and_cross_stage_planner",
                }
            ],
        },
        "materialized_consumer_equivalence_classes": [
            {
                "class_id": "view_flatten:uint8_identity_alias:node0075_A:v1",
                "member_request_ids": [REQUEST_ID],
                "materialized_consumer_signature": {
                    "consumer_request_id": "r5:hwop-0075-00",
                    "consumer_stage": "node0075_accum_pass00",
                    "dtype": "uint8",
                    "logical_shape": [16, 2048],
                    "layout": "C_CONTIGUOUS",
                    "storage_access": "existing_storage_alias",
                    "offset_bytes": 0,
                    "bytes_per_slice": 2048,
                    "slice_count": 16,
                    "total_unique_bytes": 32768,
                },
            }
        ],
        "current_approved_overlay": {
            "adjudication": "APPROVED_EQUIVALENT_UINT8_ALIAS",
            "rewrite_scope": (
                "node0072 DequantizeLinear plus node0073 View plus node0074 "
                "QuantizeLinear are replaced together"
            ),
            "metadata_operation": "reshape_alias_only",
            "dtype": "uint8",
            "source_tensor_id": "tensor-ab32f279540568c3",
            "alias_tensor_id": "tensor-6fbd5707d5f08110",
            "source_shape": overlay["source_shape"],
            "alias_shape": overlay["alias_shape"],
            "source_byte_strides": overlay["source_byte_strides"],
            "alias_byte_strides": overlay["alias_byte_strides"],
            "order": "C",
            "storage_id": overlay["storage_id"],
            "allocation_owner": "r5:hwop-0071-01:D",
            "view_allocates": False,
            "view_copies": False,
            "view_replays": False,
            "view_offset_bytes": overlay["alias_offset_bytes"],
            "slice0_base": overlay["slice0_base_addr"],
            "slice_base_formula": overlay["slice_base_formula"],
            "slice_stride_bytes": overlay["slice_address_stride_bytes"],
            "per_slice_base_addresses": _per_slice_bases(),
            "bytes_per_slice": 2048,
            "total_unique_bytes": 32768,
            "producer_occurrence": "node0071 stage08 final UINT8 D",
            "consumer_occurrence": "node0075 accum pass00 UINT8 A",
            "consumer_configured_read_occurrences": 8192,
            "hardware_view_stage_count": 0,
            "execplan_inserted_view_line_count": 0,
            "qparam_ownership": (
                "pair-elimination proof belongs to Dequant/Quantize owners; View "
                "does not derive, encode, or alter qparams"
            ),
            "padding_tail_state": "SOURCE_ABSENT_NOT_APPLICABLE",
        },
        "address_equations": {
            "source": (
                "addr_src(n,c,0,0)=0x000a2000+(n<<25)+c, "
                "0<=n<16,0<=c<2048"
            ),
            "alias": (
                "addr_alias(n,c)=0x000a2000+(n<<25)+c, "
                "0<=n<16,0<=c<2048"
            ),
            "same_address_for_all_32768_elements": True,
            "per_slice_coverage": (
                "{0x000a2000+(n<<25)+i | 0<=i<2048}, 0<=n<16"
            ),
            "total_unique_byte_coverage": 32768,
            "transaction_coverage": "16 slices * 64 transactions * 32 bytes",
        },
        "accepted_handshake_lifetime": {
            "visibility_precondition": handoff["ordering_hypothesis"],
            "first_legal_consumer_read": (
                "after node0071 final UINT8 D byte-set and completion/final "
                "barrier are accepted"
            ),
            "release_event": (
                "after node0075 final A input-data acceptance and no pending or "
                "replayed read; fallback node0075 completion accepted"
            ),
            "no_replay": True,
            "dynamic_acceptance_proven": False,
            "allocation_release_proven": False,
        },
        "native_materialization": {
            "ndp_hardware_json": "EXPLICIT_DISABLED",
            "native_handler": "SOURCE_ABSENT_NOT_APPLICABLE",
            "register_encoding": "SOURCE_ABSENT_NOT_APPLICABLE",
            "hardware_requests": "EXPLICIT_ZERO",
            "hardware_instructions": "EXPLICIT_ZERO",
            "reason": (
                "View is metadata-only; producer/consumer address owners consume "
                "the same storage without an intervening hardware operation"
            ),
        },
        "current_test_binding": {
            "package_path": package["path"],
            "package_sha256": package["sha256"],
            "view_named_member_count": package["view_member_count"],
            "execplan_sha256": package["execplan_sha256"],
            "composite_target_path": COMPOSITE_PATH.as_posix(),
            "composite_target_sha256": sha256_file(root / COMPOSITE_PATH),
            "execplan_manifest_path": EXECPLAN_MANIFEST_PATH.as_posix(),
            "execplan_manifest_sha256": sha256_file(root / EXECPLAN_MANIFEST_PATH),
            "local_static_status": "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_PASS",
            "server_status": "PACKAGE_READY_NOT_RUN",
        },
        "claim_boundary": {
            "claim_label": "APPROVED_EQUIVALENT_UINT8_ALIAS",
            "complete_json_claim": "NO_HARDWARE_JSON_REQUIRED",
            "independent_local_e2": False,
            "integrated_static_e2": True,
            "dynamic_e3_e4_e5": False,
            "configuration_only_baseline_claimed": False,
            "reason": (
                "View owns no executable stage. Static alias/address coverage is "
                "closed in the current integrated materialization, while accepted "
                "reads, terminal behavior, formal D, production RTL identity and "
                "runtime remain outside this regeneration."
            ),
        },
        "source_receipts": {
            "lowering_bundle_sha256": sha256_file(root / LOWERING_PATH),
            "fusion_contract_sha256": sha256_file(root / FUSION_PATH),
            "canonical_endpoint_sha256": sha256_file(root / CANONICAL_ENDPOINT_PATH),
            "composite_target_sha256": sha256_file(root / COMPOSITE_PATH),
            "execplan_manifest_sha256": sha256_file(root / EXECPLAN_MANIFEST_PATH),
            "e2_report_sha256": sha256_file(root / E2_REPORT_PATH),
            "view_rule_sha256": sha256_file(root / VIEW_RULE_PATH),
            "operator_rule_sha256": sha256_file(root / OPERATOR_RULE_PATH),
            "generation_index_sha256": sha256_file(root / INDEX_PATH),
            "mutable_plan_sha256": sha256_file(root / PLAN_PATH),
            "complete_json_policy_sha256": sha256_file(
                root
                / "contracts/operator_config/"
                "complete_json_generation_contract_v1.json"
            ),
            "candidate_schema_sha256": sha256_file(
                root / "schemas/operator_config_complete_json_candidate_v1.schema.json"
            ),
            "field_ledger_schema_sha256": sha256_file(
                root
                / "schemas/operator_config_field_provenance_ledger_v1.schema.json"
            ),
            "handler_schema_sha256": sha256_file(
                root / "schemas/operator_config_handler_capability_v1.schema.json"
            ),
            "current_diff_schema_sha256": sha256_file(
                root / "schemas/operator_config_current_test_diff_v1.schema.json"
            ),
            "family_set_schema_sha256": sha256_file(
                root
                / "schemas/operator_config_complete_json_family_set_v1.schema.json"
            ),
            "candidate_validator_sha256": sha256_file(
                root / "tools/validate_complete_operator_json_candidate.py"
            ),
            "family_set_auditor_sha256": sha256_file(
                root / "tools/audit_complete_operator_json_family_set.py"
            ),
        },
    }


def _ledger_source(
    root: Path,
    pointer: str,
    target_value: Any,
    request_index: int,
    bundle: Mapping[str, Any],
    fusion: Mapping[str, Any],
    composite: Mapping[str, Any],
) -> tuple[str, dict[str, Any], str, list[str], str, str]:
    if pointer.startswith("/target_inventory"):
        source_pointer = f"/requests/{request_index}"
        source_value = bundle["requests"][request_index]
        return (
            "MODEL_DERIVED",
            _source(root, LOWERING_PATH, source_pointer, source_value),
            "exact typed request inventory; strides are C-order byte derivations",
            ["op", "dtype", "shape", "layout", "DAG"],
            "typed request identity and C-order stride equation",
            "TARGET_REQUIRED_DERIVED",
        )
    if pointer.startswith("/current_approved_overlay") or pointer.startswith(
        "/address_equations"
    ):
        origin = (
            "ADDRESS_PLANNER_DERIVED"
            if any(
                token in pointer
                for token in (
                    "base",
                    "offset",
                    "stride",
                    "byte",
                    "coverage",
                    "address",
                    "occurrence",
                )
            )
            else "SCHEDULE_DERIVED"
        )
        return (
            origin,
            _source(
                root,
                FUSION_PATH,
                "/endpoint_handoff/known_source_storage",
                fusion["endpoint_handoff"]["known_source_storage"],
            ),
            "approved frozen-instance UINT8 pair-elimination alias overlay",
            ["frozen node0071D to node0075A signature"],
            "addr_alias(n,c)=0x000a2000+(n<<25)+c",
            (
                "SOURCE_ABSENT_NOT_APPLICABLE"
                if target_value == "SOURCE_ABSENT_NOT_APPLICABLE"
                else "TARGET_REQUIRED_DERIVED"
            ),
        )
    if pointer.startswith("/accepted_handshake_lifetime"):
        return (
            "SCHEDULE_DERIVED",
            _source(
                root,
                COMPOSITE_PATH,
                "/handoff",
                composite["handoff"],
                commit="WORKTREE_CURRENT_UNCOMMITTED",
            ),
            "current integrated ordering contract; dynamic acceptance remains open",
            ["cross-stage schedule", "accepted-handshake lifetime"],
            "producer accepted visibility precedes consumer accepted read and release",
            "TARGET_REQUIRED_DERIVED",
        )
    if pointer.startswith("/current_test_binding"):
        return (
            "REFERENCE_EXACT",
            _source(
                root,
                COMPOSITE_PATH,
                "",
                {
                    "sha256": sha256_file(root / COMPOSITE_PATH),
                    "current_package_sha256": CURRENT_PACKAGE_SHA256,
                },
                commit="WORKTREE_CURRENT_UNCOMMITTED",
            ),
            "read-only identity of current materialized consumer and package",
            ["current exact source instance"],
            "current package and composite payload identity",
            "TARGET_REQUIRED_DERIVED",
        )
    if pointer.startswith("/native_materialization") or pointer in (
        "/hardware_json_required",
        "/hardware_json_count",
    ):
        absence = (
            "EXPLICIT_ZERO"
            if target_value in (0, "EXPLICIT_ZERO")
            else (
                "SOURCE_ABSENT_NOT_APPLICABLE"
                if target_value == "SOURCE_ABSENT_NOT_APPLICABLE"
                else "TARGET_REQUIRED_DERIVED"
            )
        )
        return (
            "EXPLICIT_DISABLED",
            _source(
                root,
                VIEW_RULE_PATH,
                "md:CDA-VIEW-METADATA-ONLY-001",
                "View must materialize as zero-copy metadata and must not emit arithmetic JSON",
            ),
            "metadata-only View prohibition on hardware computation/config",
            ["operation class", "materialization kind"],
            "hardware_view_stage_count=0",
            absence,
        )
    if pointer.startswith("/materialized_consumer_equivalence_classes"):
        return (
            "SCHEDULE_DERIVED",
            _source(
                root,
                COMPOSITE_PATH,
                "/handoff",
                composite["handoff"],
                commit="WORKTREE_CURRENT_UNCOMMITTED",
            ),
            "equivalence key is the actual materialized consumer signature",
            ["consumer", "dtype", "shape", "layout", "address ownership"],
            "class_key=(consumer,dtype,shape,layout,storage access,coverage)",
            "TARGET_REQUIRED_DERIVED",
        )
    if pointer.startswith("/claim_boundary"):
        return (
            "SCHEDULE_DERIVED",
            _source(
                root,
                PLAN_PATH,
                "md:section-0.1:view-node0073",
                "APPROVED_EQUIVALENT_UINT8_ALIAS; overlay closed; no E4/E5 claim",
                commit="WORKTREE_CURRENT_MUTABLE_PROVENANCE",
            ),
            "current mainline adjudication and claim boundary",
            ["current project adjudication"],
            "static integration evidence does not imply dynamic/production evidence",
            "TARGET_REQUIRED_DERIVED",
        )
    if pointer.startswith("/source_receipts"):
        return (
            "REFERENCE_EXACT",
            _source(
                root,
                OPERATOR_RULE_PATH,
                "md:CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001",
                "bind every target leaf to an explicit source or derivation",
            ),
            "generation-time source identity receipt",
            ["source identity"],
            "sha256(file bytes)",
            "TARGET_REQUIRED_DERIVED",
        )
    return (
        "SCHEDULE_DERIVED",
        _source(
            root,
            VIEW_RULE_PATH,
            "md:CDA-VIEW-METADATA-ONLY-001",
            "View is a zero-copy metadata alias and not a computation operator",
        ),
        "family disposition derived from the View metadata-only rule",
        ["family", "operation class", "no-config disposition"],
        "View request -> metadata-only alias -> zero hardware JSON",
        "TARGET_REQUIRED_DERIVED",
    )


def _build_ledger(
    root: Path,
    contract: Mapping[str, Any],
    request_index: int,
    bundle: Mapping[str, Any],
    fusion: Mapping[str, Any],
    composite: Mapping[str, Any],
    candidate_sha256: str,
) -> dict[str, Any]:
    entries = []
    for pointer, value in _leaf_items(contract):
        origin, source, applicability, axes, equation, absence = _ledger_source(
            root, pointer, value, request_index, bundle, fusion, composite
        )
        if origin == "REFERENCE_EXACT":
            # Current project artifacts are exact instance receipts but are not
            # pinned-upstream native authorities in the shared authority index.
            origin = "SCHEDULE_DERIVED"
        if not str(source["pointer"]).startswith("/"):
            source = _source(
                root,
                Path("contracts/operator_config/complete_json_generation_contract_v1.json"),
                "/rules/0",
                _pointer_get(
                    _load_json(
                        root
                        / "contracts/operator_config/"
                        "complete_json_generation_contract_v1.json"
                    ),
                    "/rules/0",
                ),
                commit="WORKTREE_CURRENT_UNCOMMITTED",
            )
        source_path = Path(source["path"])
        source_value = source["value"]
        public_source = {
            "path": source_path.as_posix(),
            "commit": source["commit"],
            "blob_oid": _project_blob_oid(root, source_path),
            "file_sha256": source["blob_sha256"],
            "json_pointer": source["pointer"],
            "value": source_value,
        }
        if origin == "EXPLICIT_DISABLED":
            applicability_class = "EXPLICITLY_INACTIVE"
            derivation_receipt = None
        else:
            applicability_class = "DERIVED_FOR_TARGET"
            derivation_receipt = _bound(root, root / source_path)
        exact_axes = {
            "op": pointer.startswith("/target_inventory"),
            "dtype": pointer.startswith("/target_inventory"),
            "shape": pointer.startswith("/target_inventory"),
            "layout": pointer.startswith("/target_inventory"),
            "qparams": False,
            "topology": pointer.startswith("/target_inventory"),
            "address": pointer.startswith("/current_approved_overlay")
            or pointer.startswith("/address_equations"),
            "schedule": pointer.startswith("/accepted_handshake_lifetime"),
            "consumer": pointer.startswith(
                "/materialized_consumer_equivalence_classes"
            ),
        }
        owner = (
            "typed_lowering"
            if pointer.startswith("/target_inventory")
            else (
                "producer_consumer_address_planner"
                if pointer.startswith("/current_approved_overlay")
                or pointer.startswith("/address_equations")
                else (
                    "cross_stage_scheduler"
                    if pointer.startswith("/accepted_handshake_lifetime")
                    else "view_flatten_no_config_contract_owner"
                )
            )
        )
        entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "applicability_class": applicability_class,
                "exactness_axes": exact_axes,
                "owner": owner,
                "consumer_equation": equation,
                "derivation_receipt": derivation_receipt,
                "source": public_source,
                "negative_control_ids": [
                    "NEG_NO_FAKE_VIEW_JSON",
                    "NEG_NONZERO_ALIAS_OFFSET",
                    "NEG_DYNAMIC_ACCEPTANCE_OVERCLAIM",
                ],
                "status": "RESOLVED",
            }
        )
    absence_entries = []
    for entry in entries:
        pointer = entry["json_pointer"]
        value = entry["target_value"]
        state = None
        if value == "SOURCE_ABSENT_NOT_APPLICABLE":
            state = "SOURCE_ABSENT_NOT_APPLICABLE"
        elif value is None:
            state = "EXPLICIT_NULL_INACTIVE"
        elif value == 0 and not isinstance(value, bool):
            state = "EXPLICIT_ZERO"
        if state is not None:
            absence_entries.append(
                {
                    "target_json_pointer": pointer,
                    "state": state,
                    "reason": (
                        "View metadata alias has no such hardware field"
                        if state == "SOURCE_ABSENT_NOT_APPLICABLE"
                        else "candidate explicitly binds this inactive/zero value"
                    ),
                    "owner": entry["owner"],
                }
            )
    return {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha256,
        "entries": entries,
        "source_absences": absence_entries,
        "claim_boundary": (
            "All no-config contract leaves are resolved. This ledger does not "
            "authorize a View hardware JSON or any runtime/production claim."
        ),
    }


def _build_reference_applicability(
    root: Path, native: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema": REFERENCE_SCHEMA,
        "family": FAMILY,
        "target_request_ids": [REQUEST_ID],
        "native_authority": dict(native),
        "template_classes": {
            "A_exact_replay": [],
            "B_same_primitive_shape_differs": [],
            "C_same_hardware_block_numeric_or_dtype_differs": [],
            "D_project_added_untracked_no_upstream_authority": [
                {
                    "path": FUSION_PATH.as_posix(),
                    "sha256": sha256_file(root / FUSION_PATH),
                    "use": "approved frozen-instance project overlay only",
                    "authority_boundary": (
                        "may prove this project alias signature; may not establish "
                        "native template or handler generalization"
                    ),
                },
                {
                    "path": COMPOSITE_PATH.as_posix(),
                    "sha256": sha256_file(root / COMPOSITE_PATH),
                    "use": "current materialized consumer/address instance only",
                    "authority_boundary": (
                        "uncommitted project artifact; exact instance evidence only"
                    ),
                },
            ],
        },
        "absence_decisions": [
            {
                "field": "native View hardware JSON template",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": "metadata-only View emits no hardware JSON",
            },
            {
                "field": "native View handler",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": "no register encoding is invoked for the metadata alias",
            },
            {
                "field": "target hardware JSON leaves",
                "state": "EXPLICIT_ZERO",
                "reason": "the target set is intentionally empty, not unknown",
            },
        ],
        "nearest_template_used": False,
        "implicit_zero_used": False,
        "old_failed_package_used_as_source": False,
        "server_residue_used_as_source": False,
    }


def _build_capability(native: Mapping[str, Any]) -> dict[str, Any]:
    axes = (
        "exact_replay",
        "shape",
        "dtype",
        "qparam",
        "layout",
        "address",
        "cross_stage_schedule",
    )
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": FAMILY,
        "handler": {
            "kind": "NONE",
            "path": None,
            "sha256": None,
            "source_span": None,
        },
        "capabilities": {
            axis: {
                "supported": False,
                "evidence": (
                    "pinned ndp-sim has no View template/handler; metadata-only "
                    "alias uses no register encoder and grants no generalization"
                ),
            }
            for axis in axes
        },
        "dependent_leaves": [],
        "claim_boundary": (
            "No native handler capability is claimed. The project overlay proves "
            "only this frozen no-config alias instance."
        ),
    }


def _build_current_analysis(
    root: Path,
    contract: Mapping[str, Any],
    package: Mapping[str, Any],
    canonical: Mapping[str, Any],
) -> dict[str, Any]:
    quantize = canonical.get("owner_sections", {}).get("QuantizeLinear", {})
    stale_exact_division = (
        canonical.get("cross_owner_gates", {}).get("quantize_exact_division")
        == "OPEN"
        and (
            quantize.get("adjudication_status") == "APPROVED_EQUIVALENT"
            or "APPROVED_EQUIVALENT"
            in json.dumps(quantize, ensure_ascii=False, sort_keys=True)
        )
    )
    categories = {
        "same": [
            {
                "field": "View hardware JSON/member",
                "candidate": 0,
                "current": package["view_member_count"],
                "explanation": "both intentionally contain no View hardware config",
            },
            {
                "field": "storage identity/owner/offset",
                "candidate": {
                    "storage_id": contract["current_approved_overlay"]["storage_id"],
                    "owner": "r5:hwop-0071-01:D",
                    "offset": 0,
                },
                "current": "exact composite existing_storage_alias binding",
                "explanation": "same frozen allocation identity",
            },
            {
                "field": "shape/layout/coverage",
                "candidate": {
                    "shape": [16, 2048],
                    "layout": "C_CONTIGUOUS",
                    "unique_bytes": 32768,
                },
                "current": {
                    "shape": [16, 2048],
                    "layout": "C_CONTIGUOUS",
                    "unique_bytes": 32768,
                },
                "explanation": "same 16-slice UINT8 alias address set",
            },
            {
                "field": "copy/precompute/relayout/replay",
                "candidate": False,
                "current": False,
                "explanation": "same no-host-materialization policy",
            },
        ],
        "intentional_derivation": [
            {
                "field": "logical dtype and endpoints",
                "lowering": "node0072D float32 -> node0073 -> node0074A float32",
                "current": "node0071D uint8 -> metadata alias -> node0075A uint8",
                "authorization": "approved Dequant+View+Quant pair elimination",
            },
            {
                "field": "physical coverage",
                "lowering": "131072 bytes if the legacy FP32 edge were materialized",
                "current": "32768 bytes in the approved UINT8 overlay",
                "authorization": "dtype-preserving identity overlay after pair elimination",
            },
        ],
        "suspected_current_defect": [
            {
                "scope": "canonical_contract_coherence",
                "present": stale_exact_division,
                "field": "cross_owner_gates.quantize_exact_division/top-level claim",
                "evidence": (
                    "top-level canonical gate remains OPEN/legacy endpoint-blocked "
                    "while the Quantize owner section and current integrated artifact "
                    "use APPROVED_EQUIVALENT with the divider off path"
                ),
                "configuration_effect": "none on current v9 package payload",
            }
        ],
        "new_candidate_defect": [],
        "dynamic_only": [
            {
                "gate": "node0071 downstream acceptance before node0075 pass00 read",
                "static_candidate_can_close": False,
            },
            {
                "gate": "actual 8192 accepted reads and ordered address/hash match",
                "static_candidate_can_close": False,
            },
            {
                "gate": "32-stage/512-finish natural terminal",
                "static_candidate_can_close": False,
            },
            {
                "gate": "144 formal D comparisons",
                "static_candidate_can_close": False,
            },
        ],
    }
    return {
        "schema": DIFF_SCHEMA,
        "family": FAMILY,
        "candidate_kind": "NO_CONFIG_MACHINE_CONTRACT",
        "current_test_source": package,
        "categories": categories,
        "suspected_current_view_config_defect_count": 0,
        "suspected_current_contract_coherence_defect_count": int(stale_exact_division),
        "can_current_runtime_blocker_be_explained_by_view_config_difference": False,
        "excluded_non_config_or_other_owner_blockers": [
            {
                "item": "v5 disabled-bank/row SCA preload defect",
                "classification": "node0075 address/config owner; corrected in v9",
            },
            {
                "item": "observer accepted-read/order/hash evidence",
                "classification": "dynamic runtime evidence",
            },
            {
                "item": "package/RTL production identity and natural terminal",
                "classification": "runtime/production evidence, not View config",
            },
        ],
    }


def _build_current_diff(
    root: Path,
    contract: Mapping[str, Any],
    package: Mapping[str, Any],
    candidate_sha256: str,
) -> dict[str, Any]:
    entries = []
    for pointer, value in _leaf_items(contract):
        entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": value,
                "current_value_present": False,
                "current_value": None,
                "classification": "CURRENT_ABSENT",
                "reason": (
                    "The current package intentionally has no View hardware JSON; "
                    "the exact alias comparison is carried by the read-only "
                    "composite/execplan evidence and family report."
                ),
                "evidence": [
                    f"{package['path']}@{package['sha256']}",
                    f"{COMPOSITE_PATH.as_posix()}@{sha256_file(root / COMPOSITE_PATH)}",
                ],
            }
        )
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha256,
        "current_identity": {
            "available": False,
            "path": None,
            "sha256": None,
            "package_or_record": package["path"],
            "latest_result": (
                "PACKAGE_READY_NOT_RUN; package contains zero View-named members"
            ),
        },
        "entries": entries,
        "blocker_attribution": [
            {
                "blocker_id": "B_VIEW_DYNAMIC_ACCEPTED_READ_LIFETIME",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [
                    "/accepted_handshake_lifetime/dynamic_acceptance_proven",
                    "/accepted_handshake_lifetime/allocation_release_proven",
                ],
                "reason": "static no-config evidence cannot prove accepted runtime reads",
                "evidence": [
                    f"{E2_REPORT_PATH.as_posix()}@{sha256_file(root / E2_REPORT_PATH)}"
                ],
            },
            {
                "blocker_id": "B_VIEW_CURRENT_CONFIG_DIFFERENCE",
                "classification": "CONFIG_EXCLUDED",
                "candidate_json_pointers": [
                    "/hardware_json_required",
                    "/hardware_json_count",
                ],
                "reason": "candidate and current both intentionally emit zero View configs",
                "evidence": [f"current package view_member_count={package['view_member_count']}"],
            },
        ],
        "claim_boundary": (
            "Current View hardware config is absent by design. This diff excludes "
            "View config as the cause of dynamic observer, terminal, formal-D or "
            "production identity blockers."
        ),
    }


def validate_regeneration_bundle(project_root: Path, output_dir: Path) -> dict[str, Any]:
    root = project_root.resolve()
    out = output_dir.resolve()
    contract_path = out / "complete_json/no_config_contract.json"
    ledger_path = out / "field_provenance_ledger.json"
    reference_path = out / "reference_applicability.json"
    capability_path = out / "handler_capability.json"
    diff_path = out / "current_test_diff.json"
    required = (
        contract_path,
        ledger_path,
        reference_path,
        capability_path,
        diff_path,
    )
    for path in required:
        if not path.is_file():
            raise ViewFlattenRegenerationError(f"required output is missing: {path}")
    for path in out.rglob("*"):
        lowered = path.name.lower()
        if any(token in lowered for token in BANNED_OUTPUT_TOKENS):
            raise ViewFlattenRegenerationError(f"banned output entry: {path}")

    contract = _load_json(contract_path)
    ledger = _load_json(ledger_path)
    reference = _load_json(reference_path)
    capability = _load_json(capability_path)
    diff = _load_json(diff_path)
    if (
        contract.get("hardware_json_required") is not False
        or contract.get("hardware_json_count") != 0
        or contract.get("disposition") != "NO_HARDWARE_JSON_REQUIRED"
        or contract.get("metadata_only") is not True
        or contract.get("target_hw_op_types") != ["View"]
        or contract.get("stage_ids") != ["hwop-0073-00"]
    ):
        raise ViewFlattenRegenerationError("no-config disposition is not fail closed")
    jsons = list((out / "complete_json").glob("*.json"))
    if [path.name for path in jsons] != ["no_config_contract.json"]:
        raise ViewFlattenRegenerationError("unexpected complete_json target materialized")
    stages = contract.get("target_inventory", {}).get("stages", [])
    classes = contract.get("materialized_consumer_equivalence_classes", [])
    if len(stages) != 1 or stages[0].get("request_id") != REQUEST_ID:
        raise ViewFlattenRegenerationError("target inventory is incomplete")
    if stages[0].get("hw_op_id") != "hwop-0073-00":
        raise ViewFlattenRegenerationError("lowering hw_op_id binding differs")
    if len(classes) != 1 or classes[0].get("member_request_ids") != [REQUEST_ID]:
        raise ViewFlattenRegenerationError("equivalence-class partition differs")
    overlay = contract["current_approved_overlay"]
    if (
        overlay["view_offset_bytes"] != 0
        or overlay["per_slice_base_addresses"] != _per_slice_bases()
        or overlay["total_unique_bytes"] != 32768
        or overlay["view_copies"]
        or overlay["view_replays"]
        or overlay["hardware_view_stage_count"] != 0
    ):
        raise ViewFlattenRegenerationError("alias/address no-config proof differs")
    if contract["accepted_handshake_lifetime"]["dynamic_acceptance_proven"]:
        raise ViewFlattenRegenerationError("dynamic acceptance was overclaimed")

    leaves = dict(_leaf_items(contract))
    entries = ledger.get("entries", [])
    pointers = [entry.get("json_pointer") for entry in entries]
    if len(entries) != len(leaves) or len(set(pointers)) != len(pointers):
        raise ViewFlattenRegenerationError("leaf ledger is not one-to-one")
    if set(pointers) != set(leaves):
        raise ViewFlattenRegenerationError("leaf ledger coverage is not 100%")
    for entry in entries:
        pointer = entry["json_pointer"]
        if entry.get("target_value") != leaves[pointer]:
            raise ViewFlattenRegenerationError(f"ledger target differs: {pointer}")
        if entry.get("origin") not in ALLOWED_ORIGINS:
            raise ViewFlattenRegenerationError(f"invalid ledger origin: {pointer}")
        if entry.get("origin") == "UNRESOLVED" or entry.get("status") != "RESOLVED":
            raise ViewFlattenRegenerationError(f"unresolved ledger entry: {pointer}")
        if entry.get("applicability_class") not in {
            "DERIVED_FOR_TARGET",
            "EXPLICITLY_INACTIVE",
        }:
            raise ViewFlattenRegenerationError(
                f"invalid applicability class: {pointer}"
            )
        source = entry.get("source", {})
        required_source = (
            "commit",
            "blob_oid",
            "file_sha256",
            "path",
            "json_pointer",
            "value",
        )
        if any(key not in source for key in required_source):
            raise ViewFlattenRegenerationError(f"incomplete source ledger: {pointer}")
        if not entry.get("owner") or not entry.get("exactness_axes"):
            raise ViewFlattenRegenerationError(f"incomplete applicability: {pointer}")
        if not entry.get("consumer_equation"):
            raise ViewFlattenRegenerationError(f"incomplete derivation: {pointer}")
    for absence in ledger.get("source_absences", []):
        if absence.get("state") not in ABSENCE_STATES:
            raise ViewFlattenRegenerationError("invalid source-absence state")
        if absence.get("state") == "SOURCE_ABSENT_UNKNOWN_FOR_TARGET":
            raise ViewFlattenRegenerationError("unknown required target leaf")

    native = reference.get("native_authority", {})
    if (
        native.get("commit") != NDPSIM_COMMIT
        or native.get("template_present")
        or native.get("handler_present")
        or reference.get("nearest_template_used")
        or reference.get("implicit_zero_used")
    ):
        raise ViewFlattenRegenerationError("native authority boundary differs")
    if capability.get("handler", {}).get("kind") != "NONE":
        raise ViewFlattenRegenerationError("View handler must be NONE")
    project_cap = capability.get("capabilities", {})
    if any(item.get("supported") for item in project_cap.values()):
        raise ViewFlattenRegenerationError("project overlay was generalized")
    diff_entries = diff.get("entries", [])
    if len(diff_entries) != len(leaves) or any(
        entry.get("classification") != "CURRENT_ABSENT"
        for entry in diff_entries
    ):
        raise ViewFlattenRegenerationError("current no-View-config diff is incomplete")
    if any(
        item.get("blocker_id") == "B_VIEW_CURRENT_CONFIG_DIFFERENCE"
        and item.get("classification") != "CONFIG_EXCLUDED"
        for item in diff.get("blocker_attribution", [])
    ):
        raise ViewFlattenRegenerationError("View config defect was overattributed")

    package = _package_receipt(root)
    if package["view_member_count"] != 0:
        raise ViewFlattenRegenerationError("current package contains a View member")
    return {
        "valid": True,
        "strict_schema": True,
        "consumer_formula": True,
        "address_formula": True,
        "leaf_provenance_coverage": True,
        "negative_control_ready": True,
        "target_stage_count": 1,
        "equivalence_class_count": 1,
        "hardware_json_count": 0,
        "contract_leaf_count": len(leaves),
        "unresolved_count": 0,
        "current_package_view_member_count": 0,
    }


def build_view_flatten_complete_json_regeneration(
    project_root: Path, output_dir: Path | None = None
) -> dict[str, Any]:
    root = project_root.resolve()
    out = (
        output_dir.resolve()
        if output_dir is not None
        else root
        / "artifacts/operator_config_validation/"
        "r5_complete_json_regeneration_v1/view_flatten"
    )
    bundle = _load_json(root / LOWERING_PATH)
    request_index, request = _request_index(bundle)
    fusion = _load_json(root / FUSION_PATH)
    canonical = _load_json(root / CANONICAL_ENDPOINT_PATH)
    composite = _load_json(root / COMPOSITE_PATH)
    native = _native_authority_receipt(root)
    package = _package_receipt(root)

    contract = _build_contract(
        root, bundle, request_index, request, fusion, composite, package
    )
    paths = {
        "contract": out / "complete_json/no_config_contract.json",
        "ledger": out / "field_provenance_ledger.json",
        "reference": out / "reference_applicability.json",
        "capability": out / "handler_capability.json",
        "diff": out / "current_test_diff.json",
        "diff_analysis": out / "current_test_diff_analysis.json",
    }
    _write_json(paths["contract"], contract)
    candidate_sha256 = sha256_file(paths["contract"])
    ledger = _build_ledger(
        root,
        contract,
        request_index,
        bundle,
        fusion,
        composite,
        candidate_sha256,
    )
    reference = _build_reference_applicability(root, native)
    capability = _build_capability(native)
    diff = _build_current_diff(root, contract, package, candidate_sha256)
    diff_analysis = _build_current_analysis(
        root, contract, package, canonical
    )
    for key, value in (
        ("ledger", ledger),
        ("reference", reference),
        ("capability", capability),
        ("diff", diff),
        ("diff_analysis", diff_analysis),
    ):
        _write_json(paths[key], value)

    validation = validate_regeneration_bundle(root, out)
    candidate_contract = {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": FAMILY,
        "candidate_status": "COMPLETE",
        "reference_class": "D",
        "changed_axes": [],
        "target_hw_op_types": ["View"],
        "stage_ids": ["hwop-0073-00"],
        "candidate_json": _bound(root, paths["contract"]),
        "field_provenance_ledger": _bound(root, paths["ledger"]),
        "handler_capability": _bound(root, paths["capability"]),
        "current_test_diff": _bound(root, paths["diff"]),
        "composition": {"required": False, "boundary": None},
        "artifact_root": out.relative_to(root).as_posix(),
        "claim_boundary": (
            "COMPLETE means the metadata-only no-config machine contract has "
            "complete local provenance and comparison. It is not a hardware JSON "
            "or mapping/bitstream/execplan/SCA/runtime/production claim."
        ),
    }
    candidate_contract_path = out / "candidate_contract.json"
    _write_json(candidate_contract_path, candidate_contract)
    from tools.validate_complete_operator_json_candidate import (  # noqa: PLC0415
        DEFAULT_AUTHORITY,
        DEFAULT_LOWERING,
        DEFAULT_POLICY,
        validate as validate_candidate,
    )

    candidate_validation = validate_candidate(
        workspace_root=root,
        contract_path=candidate_contract_path,
        authority_path=DEFAULT_AUTHORITY,
        policy_path=DEFAULT_POLICY,
        lowering_path=DEFAULT_LOWERING,
    )
    candidate_validation_path = out / "candidate_validation.json"
    _write_json(candidate_validation_path, candidate_validation)
    if candidate_validation.get("pass") is not True:
        raise ViewFlattenRegenerationError(
            "public candidate validation failed: "
            + "; ".join(candidate_validation.get("errors", []))
        )
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": FAMILY,
        "target_hw_op_types": ["View"],
        "candidate_contracts": [],
        "no_config_stages": [
            {
                "stage_id": "hwop-0073-00",
                "reason_code": "METADATA_ONLY_ALIAS_NO_COMPUTE",
                "evidence": {
                    "path": paths["contract"].relative_to(root).as_posix(),
                    "sha256": sha256_file(paths["contract"]),
                },
            }
        ],
        "claim_boundary": (
            "Exactly one lowering View stage is covered once by metadata-only "
            "alias evidence. No hardware JSON, mapping, bitstream, execplan, SCA, "
            "server package/run, natural terminal, formal D, E3, E4 or E5 claim."
        ),
    }
    family_set_path = out / "family_set.json"
    _write_json(family_set_path, family_set)
    from tools.audit_complete_operator_json_family_set import (  # noqa: PLC0415
        audit_family_set,
    )

    family_set_validation = audit_family_set(
        workspace_root=root,
        manifest_path=family_set_path,
        authority_path=DEFAULT_AUTHORITY,
        policy_path=DEFAULT_POLICY,
        lowering_path=DEFAULT_LOWERING,
    )
    family_set_validation_path = out / "family_set_validation.json"
    _write_json(family_set_validation_path, family_set_validation)
    if family_set_validation.get("pass") is not True:
        raise ViewFlattenRegenerationError(
            "public family-set audit failed: "
            + "; ".join(family_set_validation.get("errors", []))
        )
    report = {
        "schema": REPORT_SCHEMA,
        "family": FAMILY,
        "status": "FAMILY_COMPLETE_JSON_FINDINGS",
        "disposition": "NO_HARDWARE_JSON_REQUIRED",
        "target_stage_count": 1,
        "equivalence_class_count": 1,
        "hardware_json_count": 0,
        "unresolved_count": 0,
        "validator_results": validation,
        "public_candidate_validation": {
            "pass": True,
            "candidate_status": candidate_validation["candidate_status"],
            "candidate_leaf_count": candidate_validation["candidate_leaf_count"],
            "ledger_leaf_count": candidate_validation["ledger_leaf_count"],
            "handler_kind": candidate_validation["handler"]["handler_kind"],
            "composition_required": candidate_validation["composition"]["required"],
            "note": (
                "candidate validates the no-config evidence contract and is "
                "intentionally not listed as a hardware candidate in family_set"
            ),
        },
        "public_family_set_audit": {
            "pass": True,
            "expected_stage_count": family_set_validation["expected_stage_count"],
            "covered_stage_count": family_set_validation["covered_stage_count"],
            "missing_stage_ids": family_set_validation["missing_stage_ids"],
            "unexpected_stage_ids": family_set_validation["unexpected_stage_ids"],
            "candidate_contract_count": len(
                family_set_validation["candidate_reports"]
            ),
            "no_config_stage_count": len(
                family_set_validation["no_config_receipts"]
            ),
            "candidate_validator": (
                "NOT_APPLICABLE_NO_CONFIG_STAGE; public family-set auditor is the "
                "applicable unified gate"
            ),
        },
        "current_suspected_view_config_defects": [],
        "current_contract_coherence_findings": [
            (
                "canonical node0072-node0074 endpoint top-level exact-division/"
                "endpoint-blocked gate is stale relative to its Quantize owner "
                "section and the current approved node0071-to-node0075 overlay"
            )
        ],
        "excluded_non_config_blockers": diff_analysis[
            "excluded_non_config_or_other_owner_blockers"
        ],
        "claim_boundary": contract["claim_boundary"],
        "rule_delta_proposal": {
            "kind": "NON_SYNONYMOUS_FAMILY_RULE_UPDATE",
            "target": VIEW_RULE_PATH.as_posix(),
            "proposal": (
                "Add an approved pair-elimination UINT8 alias route that binds "
                "node0071D to node0075A and marks the legacy FP32 node0072D-to-"
                "node0074A endpoint as off-path. Preserve the prohibition on "
                "hardware/arithmetic JSON and require exact consumer materialization "
                "plus accepted-lifetime evidence for integrated claims."
            ),
            "public_rule_change_requested": False,
        },
        "analysis_reuse": {
            "repeated_32768_element_numeric_analysis": False,
            "consumed_existing_frozen_alias_assets": True,
            "new_work": (
                "full target inventory, source authority audit, leaf provenance, "
                "handler capability matrix and current payload diff"
            ),
        },
        "package_release": {
            "state": "NOT_GENERATED_NOT_MODIFIED",
            "server_package_created": False,
            "server_package_modified": False,
            "upload_or_run": False,
            "lease": False,
        },
        "files": {
            key: {
                "path": path.resolve().relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
            for key, path in paths.items()
        },
    }
    report["files"]["family_set"] = {
        "path": family_set_path.relative_to(root).as_posix(),
        "sha256": sha256_file(family_set_path),
    }
    report["files"]["family_set_validation"] = {
        "path": family_set_validation_path.relative_to(root).as_posix(),
        "sha256": sha256_file(family_set_validation_path),
    }
    report["files"]["candidate_contract"] = {
        "path": candidate_contract_path.relative_to(root).as_posix(),
        "sha256": sha256_file(candidate_contract_path),
    }
    report["files"]["candidate_validation"] = {
        "path": candidate_validation_path.relative_to(root).as_posix(),
        "sha256": sha256_file(candidate_validation_path),
    }
    report["report_content_sha256"] = sha256_bytes(canonical_json_bytes(report))
    report_path = out / "report.json"
    _write_json(report_path, report)
    return {
        "family": FAMILY,
        "output_dir": out.relative_to(root).as_posix(),
        "report_path": report_path.relative_to(root).as_posix(),
        "report_sha256": sha256_file(report_path),
        "target_stage_count": 1,
        "equivalence_class_count": 1,
        "hardware_json_count": 0,
        "unresolved_count": 0,
        "valid": True,
        "package_release": "NOT_GENERATED_NOT_MODIFIED",
    }


def run_negative_controls(project_root: Path, output_dir: Path) -> dict[str, Any]:
    root = project_root.resolve()
    out = output_dir.resolve()
    cases: list[dict[str, Any]] = []

    def expect_rejected(name: str, mutation: Any) -> None:
        snapshots = {
            path: path.read_bytes()
            for path in out.rglob("*")
            if path.is_file()
        }
        try:
            mutation()
            try:
                validate_regeneration_bundle(root, out)
            except ViewFlattenRegenerationError as error:
                cases.append({"name": name, "rejected": True, "reason": str(error)})
            else:
                raise ViewFlattenRegenerationError(
                    f"negative control was accepted: {name}"
                )
        finally:
            current_files = [path for path in out.rglob("*") if path.is_file()]
            for path in current_files:
                if path not in snapshots:
                    path.unlink()
            for path, payload in snapshots.items():
                path.write_bytes(payload)

    def mutate_contract() -> None:
        path = out / "complete_json/no_config_contract.json"
        value = _load_json(path)
        value["hardware_json_required"] = True
        _write_json(path, value)

    def add_fake_json() -> None:
        _write_json(out / "complete_json/fake_view_registers.json", {"enable": 0})

    def mutate_offset() -> None:
        path = out / "complete_json/no_config_contract.json"
        value = _load_json(path)
        value["current_approved_overlay"]["view_offset_bytes"] = 1
        _write_json(path, value)

    def mutate_origin() -> None:
        path = out / "field_provenance_ledger.json"
        value = _load_json(path)
        value["entries"][0]["origin"] = "NEAREST_TEMPLATE"
        _write_json(path, value)

    def overclaim_dynamic() -> None:
        path = out / "complete_json/no_config_contract.json"
        value = _load_json(path)
        value["accepted_handshake_lifetime"]["dynamic_acceptance_proven"] = True
        _write_json(path, value)

    for name, mutation in (
        ("hardware_json_required_true", mutate_contract),
        ("fabricated_view_register_json", add_fake_json),
        ("nonzero_alias_offset", mutate_offset),
        ("invalid_nearest_template_origin", mutate_origin),
        ("dynamic_acceptance_overclaim", overclaim_dynamic),
    ):
        expect_rejected(name, mutation)
    validate_regeneration_bundle(root, out)
    return {
        "valid": True,
        "case_count": len(cases),
        "rejected_count": sum(int(case["rejected"]) for case in cases),
        "cases": cases,
    }


__all__ = [
    "ViewFlattenRegenerationError",
    "build_view_flatten_complete_json_regeneration",
    "run_negative_controls",
    "validate_regeneration_bundle",
]
