from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


FAMILY = "conv_int32_accumulate"
OUTPUT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/conv_int32_accumulate"
)
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
LIFETIME_REL = Path("contracts/operator_config/stage_state_lifetime_contract_v1.json")
EXPANSION_REL = Path("contracts/operator_config/conv_sa_remaining52_expansion_v1.json")
SERIALIZED_CONFIG_REL = Path(
    "configs/native_ndp_sim/node0004_transout_threshold_fix_c0_v5/"
    "accumulate_waves/wave-0.json"
)
NATIVE_CONFIG_REL = Path(
    "configs/native_ndp_sim/r5_conv_native_four_lane_df23e4d_v1/"
    "accumulate_waves/wave-0.json"
)
SERIALIZED_PACKAGE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v48_lc9_actual.zip"
)
NATIVE_PACKAGE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_0cc_p8f.zip"
)
UPSTREAM_REFERENCE_RELS = (
    Path("jsons/prefill_gemm_local.json"),
    Path("jsons/decode_gemv_local.json"),
    Path("jsons/gemv_config_local_M1N128K32.json"),
)
PROJECT_RULE_RELS = (
    Path(".agents/agent.md"),
    Path(".agents/plan.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
)
ORIGIN_ENUM = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bound(project_root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.resolve().relative_to(project_root.resolve()).as_posix(),
        "sha256": sha256_file(path),
    }


def git(project_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=project_root, text=True, encoding="utf-8"
    ).strip()


def ndp_git(project_root: Path, *args: str) -> str:
    ndp_root = (project_root / "ndp-sim").resolve()
    return subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={ndp_root.as_posix()}",
            "-C",
            str(ndp_root),
            *args,
        ],
        cwd=project_root,
        text=True,
        encoding="utf-8",
    ).strip()


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def flatten_json(value: Any, pointer: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    if isinstance(value, dict):
        if not value:
            leaves[pointer or "/"] = {}
        for key in sorted(value):
            child = f"{pointer}/{pointer_escape(str(key))}"
            leaves.update(flatten_json(value[key], child))
    elif isinstance(value, list):
        if not value:
            leaves[pointer or "/"] = []
        for index, item in enumerate(value):
            leaves.update(flatten_json(item, f"{pointer}/{index}"))
    else:
        leaves[pointer or "/"] = value
    return leaves


def nullify_json_leaves(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: nullify_json_leaves(item) for key, item in value.items()}
    if isinstance(value, list):
        return [nullify_json_leaves(item) for item in value]
    return None


def typed_parameter(request: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item for item in request["typed_parameters"] if item.get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{request['request_id']} has {len(matches)} {name}")
    return matches[0]


def port(request: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [
        item for item in request["ports"]["inputs"] if item.get("role") == role
    ]
    if len(matches) != 1:
        raise ValueError(f"{request['request_id']} has {len(matches)} {role}")
    return matches[0]


def consumer_equation(pointer: str) -> str:
    if pointer == "/CONFIG":
        return "CONFIG enables the materialized LC/MSE/buffer/SA topology"
    if pointer.startswith("/dram_loop_configs/"):
        return "LC emits the configured start/stride/end sequence and last_index"
    if pointer.startswith("/lc_pe_configs/"):
        return "LC-PE consumes declared sources/modes and emits index/control values"
    if pointer.startswith("/buffer_loop_configs/"):
        return "buffer row/column address = configured loop state and stride"
    if pointer.startswith("/buffer_config/"):
        return "buffer valid/full/reuse/release follows mode, mask, capacity and lifetime"
    if pointer.startswith("/stream_engine/"):
        return "byte_address = base_addr + sum(index_i * dim_stride_i), then target buffer mapping"
    if pointer.startswith("/n2n/"):
        return "N2N route/tag/terminal follows the explicit connectivity leaf"
    if pointer.startswith("/special_array/"):
        return "SA operand/control/terminal consumer reads the encoded special_array leaf"
    if pointer.startswith("/gemm_shape/") or pointer.startswith("/gemv_shape/"):
        return "reference-only logical shape annotation; not a Conv target consumer leaf"
    return "strict JSON consumer equation is not proven for this target pointer"


def applicability_axes(level: str) -> dict[str, bool]:
    if level == "A":
        return {
            "op": True,
            "dtype": True,
            "shape": True,
            "layout": True,
            "qparam": True,
            "address": True,
            "schedule": True,
        }
    if level == "B":
        return {
            "op": True,
            "dtype": True,
            "shape": False,
            "layout": False,
            "qparam": False,
            "address": False,
            "schedule": False,
        }
    if level == "C":
        return {
            "op": False,
            "dtype": False,
            "shape": False,
            "layout": False,
            "qparam": False,
            "address": False,
            "schedule": False,
        }
    return {
        "op": False,
        "dtype": False,
        "shape": False,
        "layout": False,
        "qparam": False,
        "address": False,
        "schedule": False,
    }


def build_stage_catalog(
    lowering: dict[str, Any], lifetime: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests = [
        request
        for request in lowering["requests"]
        if request["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    ]
    if len(requests) != 53:
        raise ValueError(f"Conv census differs: {len(requests)}")

    dag_by_node = {item["node_id"]: item for item in lowering["node_stage_dags"]}
    edges = lifetime["typed_tensor_dag"]["edges"]
    incoming_by_consumer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing_by_producer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        incoming_by_consumer[edge["consumer_request_id"]].append(edge)
        outgoing_by_producer[edge["producer_request_id"]].append(edge)

    stages: list[dict[str, Any]] = []
    groups: dict[str, list[str]] = defaultdict(list)
    group_payloads: dict[str, dict[str, Any]] = {}
    for ordinal, request in enumerate(requests):
        identity = request["identity"]
        geometry = request["logical_geometry"]
        attrs = geometry["attributes"]
        x = port(request, "x")
        w = port(request, "w")
        wzp = port(request, "w_zero_point")
        bias = port(request, "bias")
        xzp_value = typed_parameter(request, "x_zero_point")["value"]
        wzp_value = typed_parameter(request, "w_zero_point")["value"]
        bias_value = typed_parameter(request, "bias")["value"]
        logical_k = math.prod(geometry["input_shapes"][2][1:])
        k_groups = math.ceil(logical_k / 4)
        request_id = request["request_id"]
        incoming = incoming_by_consumer.get(request_id, [])
        outgoing = outgoing_by_producer.get(request_id, [])
        x_edges = [edge for edge in incoming if edge["tensor_id"] == x["tensor_id"]]
        x_owner = (
            x_edges[0]["producer_request_id"]
            if len(x_edges) == 1
            else (
                "graph_input"
                if x.get("kind") == "graph_input"
                else "UNRESOLVED_PHYSICAL_PRODUCER"
            )
        )
        output = request["ports"]["outputs"][0]
        stage_qparams = {
            "x_zero_point": xzp_value,
            "w_zero_point": wzp_value,
            "bias": bias_value,
        }
        signature = {
            "op": identity["hw_op_type"],
            "dtype": {
                "inputs": geometry["input_dtypes"],
                "outputs": geometry["output_dtypes"],
            },
            "shape": {
                "inputs": geometry["input_shapes"],
                "outputs": geometry["output_shapes"],
            },
            "layout": {
                "activation": "NCHW_LOGICAL_ONLY",
                "weight": "OIHW_LOGICAL_ONLY",
                "output": "NCHW_LOGICAL_ONLY",
                "physical": "UNRESOLVED",
            },
            "qparams": {
                "x_zero_point_scalar": xzp_value["scalar"],
                "weight_zero_point_dtype": wzp_value["dtype"],
                "weight_zero_point_shape": wzp_value["shape"],
                "weight_zero_point_minimum": wzp_value["minimum"],
                "weight_zero_point_maximum": wzp_value["maximum"],
                "bias_present": True,
                "bias_dtype": bias_value["dtype"],
                "bias_shape": bias_value["shape"],
            },
            "padding_tail": {
                "pads": attrs["pads"],
                "strides": attrs["strides"],
                "dilations": attrs["dilations"],
                "group": attrs["group"],
                "logical_k": logical_k,
                "dot4_groups": k_groups,
                "tail_lane_count": logical_k % 4,
                "padded_zero_product_lanes": k_groups * 4 - logical_k,
                "activation_padding_value": xzp_value["scalar"],
                "weight_padding_value": 0,
            },
        }
        signature_id = canonical_sha256(signature)
        groups[signature_id].append(identity["hw_op_id"])
        group_payloads[signature_id] = signature
        stages.append(
            {
                "ordinal": ordinal,
                "request_id": request_id,
                "request_sha256": request["request_sha256"],
                "identity": identity,
                "materialized_consumer_signature_id": signature_id,
                "op": identity["hw_op_type"],
                "dtype": signature["dtype"],
                "shape": signature["shape"],
                "layout": signature["layout"],
                "qparams": stage_qparams,
                "padding_tail": signature["padding_tail"],
                "dag": {
                    "node_stage_ids": dag_by_node[identity["node_id"]]["stage_ids"],
                    "node_internal_edges": dag_by_node[identity["node_id"]][
                        "internal_edges"
                    ],
                    "typed_predecessor_request_ids": sorted(
                        {edge["producer_request_id"] for edge in incoming}
                    ),
                    "typed_consumer_request_ids": sorted(
                        {edge["consumer_request_id"] for edge in outgoing}
                    ),
                },
                "address_owner": {
                    "activation": {
                        "tensor_id": x["tensor_id"],
                        "logical_owner": x_owner,
                        "physical_owner": "UNRESOLVED",
                    },
                    "weight": {
                        "tensor_id": w["tensor_id"],
                        "logical_owner": f"onnx_initializer:{w['onnx_name']}",
                        "physical_owner": "UNRESOLVED",
                    },
                    "weight_zero_point": {
                        "tensor_id": wzp["tensor_id"],
                        "logical_owner": f"onnx_initializer:{wzp['onnx_name']}",
                        "physical_owner": "UNRESOLVED",
                    },
                    "bias": {
                        "tensor_id": bias["tensor_id"],
                        "logical_owner": f"onnx_initializer:{bias['onnx_name']}",
                        "physical_owner": "UNRESOLVED",
                    },
                    "output_int32": {
                        "tensor_id": output["tensor_id"],
                        "logical_owner": request_id,
                        "physical_owner": "UNRESOLVED",
                    },
                },
                "lifetime": {
                    "visibility_requirement": (
                        "all producer bytes accepted plus producer completion/final barrier"
                    ),
                    "first_legal_read": "after visibility requirement",
                    "release_requirement": (
                        "after final input-data accepted and no pending/replayed read"
                    ),
                    "physical_binding_status": "UNRESOLVED",
                    "typed_edge_statuses": sorted(
                        {
                            edge["physical_allocation_status"]
                            for edge in incoming + outgoing
                        }
                    ),
                },
                "typed_source_ownership": {
                    role: {
                        "tensor_id": item["tensor_id"],
                        "identity_sha256": item["identity_sha256"],
                        "identity_source": item["identity_source"],
                    }
                    for role, item in (
                        ("activation", x),
                        ("weight", w),
                        ("weight_zero_point", wzp),
                        ("bias", bias),
                    )
                },
                "strict_json_materialization_status": (
                    "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED"
                ),
            }
        )

    equivalence_classes = [
        {
            "signature_id": signature_id,
            "member_count": len(members),
            "member_hw_op_ids": members,
            "signature": group_payloads[signature_id],
        }
        for signature_id, members in sorted(groups.items())
    ]
    return stages, equivalence_classes


def build_references(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    ndp_commit = ndp_git(project_root, "rev-parse", "HEAD")
    project_commit = git(project_root, "rev-parse", "HEAD")
    references: list[dict[str, Any]] = []
    upstream_leaf_sources: dict[str, dict[str, Any]] = {}
    for relative in UPSTREAM_REFERENCE_RELS:
        full = project_root / "ndp-sim" / relative
        blob = ndp_git(project_root, "rev-parse", f"HEAD:{relative.as_posix()}")
        status = ndp_git(
            project_root, "status", "--short", "--", relative.as_posix()
        )
        value = load_json(full)
        leaves = flatten_json(value)
        classification = "C"
        references.append(
            {
                "path": f"ndp-sim/{relative.as_posix()}",
                "source_repository": "ndp-sim",
                "source_commit": ndp_commit,
                "source_blob": blob,
                "sha256": sha256_file(full),
                "worktree_status": status,
                "template_level": classification,
                "applicability": (
                    "same SA hardware family, but FP16 GEMM/GEMV numeric/dtype/"
                    "shape/layout/address/schedule are not INT8 Conv authority"
                ),
                "exact_replay_target_count": 0,
            }
        )
        if relative == UPSTREAM_REFERENCE_RELS[0]:
            for pointer, source_value in leaves.items():
                upstream_leaf_sources[pointer] = {
                    "repository": "ndp-sim",
                    "commit": ndp_commit,
                    "blob": blob,
                    "file": f"ndp-sim/{relative.as_posix()}",
                    "pointer": pointer,
                    "value": source_value,
                }

    project_sources: dict[str, dict[str, Any]] = {}
    for level, relative in (
        ("D", SERIALIZED_CONFIG_REL),
        ("D", NATIVE_CONFIG_REL),
    ):
        full = project_root / relative
        blob = git(project_root, "ls-files", "--stage", "--", relative.as_posix())
        blob_id = blob.split()[1] if blob else None
        references.append(
            {
                "path": relative.as_posix(),
                "source_repository": "project",
                "source_commit": project_commit,
                "source_blob": blob_id,
                "sha256": sha256_file(full),
                "worktree_status": git(
                    project_root, "status", "--short", "--", relative.as_posix()
                ),
                "template_level": level,
                "applicability": (
                    "project-added instance-specific current comparison input; "
                    "not upstream authority and never used as target_value provenance"
                ),
                "exact_replay_target_count": 0,
            }
        )
        for pointer, source_value in flatten_json(load_json(full)).items():
            project_sources.setdefault(
                pointer,
                {
                    "repository": "project",
                    "commit": project_commit,
                    "blob": blob_id,
                    "file": relative.as_posix(),
                    "pointer": pointer,
                    "value": source_value,
                },
            )

    registry_rel = Path("model_execplan/config/operator_base_info.json")
    registry_head = ndp_git(
        project_root, "show", f"HEAD:{registry_rel.as_posix()}"
    )
    registry_work = (project_root / "ndp-sim" / registry_rel).read_text(
        encoding="utf-8"
    )
    references.append(
        {
            "path": f"ndp-sim/{registry_rel.as_posix()}",
            "source_repository": "ndp-sim",
            "source_commit": ndp_commit,
            "source_blob": ndp_git(
                project_root, "rev-parse", f"HEAD:{registry_rel.as_posix()}"
            ),
            "sha256": sha256_file(project_root / "ndp-sim" / registry_rel),
            "worktree_status": ndp_git(
                project_root, "status", "--short", "--", registry_rel.as_posix()
            ),
            "template_level": "D_FOR_WORKTREE_ADDITIONS",
            "head_has_conv": (
                "QLinearConv" in registry_head
                or "ConvInt32Accumulate" in registry_head
            ),
            "worktree_has_conv": (
                "QLinearConv" in registry_work
                or "ConvInt32Accumulate" in registry_work
            ),
            "worktree_has_project_matmul": "MatMulInt32Accumulate" in registry_work,
        }
    )
    return (
        {
            "schema": "conv53-reference-applicability-v1",
            "family": FAMILY,
            "classification": {
                "A_exact_replay_stage_count": 0,
                "B_same_primitive_shape_diff_stage_count": 0,
                "C_same_hardware_numeric_dtype_diff_stage_count": 53,
                "D_project_added_untracked_or_no_authority_stage_count": 53,
                "note": (
                    "C and D are reference classifications, not cumulative target "
                    "authorization; every stage lacks A/B authority"
                ),
            },
            "references": references,
            "prohibited_numeric_authority": [
                "FP16 GEMM",
                "FP16 GEMV",
                "project-added node0004 JSON",
                "old failed server packages",
                "server residual files",
            ],
        },
        {
            "upstream_leaf_sources": upstream_leaf_sources,
            "project_leaf_sources": project_sources,
            "ndp_commit": ndp_commit,
            "project_commit": project_commit,
        },
    )


def build_capability_matrix(
    project_root: Path, reference_state: dict[str, Any]
) -> dict[str, Any]:
    safe_root = (project_root / "ndp-sim").resolve().as_posix()
    tracked_conv = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe_root}",
            "-C",
            str(project_root / "ndp-sim"),
            "grep",
            "-n",
            "-E",
            "QLinearConv|ConvInt32Accumulate",
            "HEAD",
            "--",
            "model_execplan",
            "jsons",
        ],
        cwd=project_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    worktree_hits = subprocess.run(
        [
            "rg",
            "-n",
            "-i",
            "QLinearConv|ConvInt32Accumulate",
            "ndp-sim/model_execplan",
            "ndp-sim/jsons",
        ],
        cwd=project_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    rows = [
        {
            "capability": "pinned_upstream_conv_handler_registry",
            "authority": "ndp-sim HEAD",
            "exact_replay": False,
            "shape": False,
            "dtype": False,
            "qparam": False,
            "layout": False,
            "address": False,
            "cross_stage_schedule": False,
            "evidence": {
                "git_grep_exit": tracked_conv.returncode,
                "git_grep_stdout": tracked_conv.stdout.strip(),
                "commit": reference_state["ndp_commit"],
            },
            "first_missing_capability": (
                "no QLinearConv/ConvInt32Accumulate JSON registry or handler"
            ),
        },
        {
            "capability": "current_ndp_sim_worktree_conv_handler_registry",
            "authority": "project working tree only",
            "exact_replay": False,
            "shape": False,
            "dtype": False,
            "qparam": False,
            "layout": False,
            "address": False,
            "cross_stage_schedule": False,
            "evidence": {
                "rg_exit": worktree_hits.returncode,
                "rg_stdout": worktree_hits.stdout.strip(),
                "working_tree_matmul_additions_do_not_authorize_conv": True,
            },
            "first_missing_capability": (
                "no Conv handler even after project-local MatMul additions"
            ),
        },
        {
            "capability": "project_node0004_instance_materializer",
            "authority": "project instance-specific D reference",
            "exact_replay": True,
            "shape": False,
            "dtype": False,
            "qparam": False,
            "layout": False,
            "address": False,
            "cross_stage_schedule": False,
            "evidence": {
                "serialized_config": SERIALIZED_CONFIG_REL.as_posix(),
                "native_config": NATIVE_CONFIG_REL.as_posix(),
            },
            "first_missing_capability": (
                "no generic equation-backed shape/address/lifetime generalization"
            ),
        },
        {
            "capability": "remaining52_schedule_inventory",
            "authority": "project list-only analysis",
            "exact_replay": False,
            "shape": True,
            "dtype": True,
            "qparam": True,
            "layout": False,
            "address": False,
            "cross_stage_schedule": False,
            "evidence": {
                "path": EXPANSION_REL.as_posix(),
                "sha256": sha256_file(project_root / EXPANSION_REL),
                "physical_address_lifetime_binding_pending": True,
            },
            "first_missing_capability": (
                "materialized physical layout/address/lifetime/execplan owner"
            ),
        },
        {
            "capability": "generic_json_mapper_encoder",
            "authority": "encoder-only",
            "exact_replay": True,
            "shape": False,
            "dtype": False,
            "qparam": False,
            "layout": False,
            "address": False,
            "cross_stage_schedule": False,
            "evidence": {
                "claim": (
                    "can encode a complete supplied JSON, cannot derive missing "
                    "semantic leaves"
                )
            },
            "first_missing_capability": (
                "semantic materializer before mapper/encoder"
            ),
        },
    ]
    return {
        "schema": "conv53-handler-capability-matrix-v1",
        "family": FAMILY,
        "rows": rows,
        "generalization_claim": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "placeholder_or_file_presence_counts_as_support": False,
    }


def build_leaf_ledger(
    project_root: Path,
    stages: list[dict[str, Any]],
    reference_state: dict[str, Any],
) -> dict[str, Any]:
    upstream = reference_state["upstream_leaf_sources"]
    project = reference_state["project_leaf_sources"]
    target_pointers = sorted(set(upstream) | set(project))
    records: list[dict[str, Any]] = []
    per_pointer_counts: Counter[str] = Counter()
    unresolved_count = 0
    not_applicable_count = 0
    for stage in stages:
        stage_records: list[dict[str, Any]] = []
        for pointer in target_pointers:
            upstream_source = upstream.get(pointer)
            project_source = project.get(pointer)
            reference = upstream_source or project_source
            if pointer.startswith("/gemm_shape/") or pointer.startswith(
                "/gemv_shape/"
            ):
                status = "SOURCE_ABSENT_NOT_APPLICABLE"
                not_applicable_count += 1
            else:
                status = "SOURCE_ABSENT_UNKNOWN_FOR_TARGET"
                unresolved_count += 1
            level = "C" if upstream_source is not None else "D"
            entry = {
                "json_pointer": pointer,
                "target_value": None,
                "origin": "UNRESOLVED",
                "source": reference,
                "applicability": {
                    "template_level": level,
                    "reason": (
                        "FP16 GEMM/GEMV same hardware only"
                        if level == "C"
                        else "project-added instance-specific field inventory only"
                    ),
                },
                "exactness_axes": applicability_axes(level),
                "derivation": (
                    "none; no authorized Conv handler/materializer equation"
                ),
                "current_consumer_equation": consumer_equation(pointer),
                "status": status,
            }
            stage_records.append(entry)
            per_pointer_counts[status] += 1
        records.append(
            {
                "request_id": stage["request_id"],
                "hw_op_id": stage["identity"]["hw_op_id"],
                "target_leaf_count": len(stage_records),
                "complete_coverage": True,
                "entries": stage_records,
            }
        )
    return {
        "schema": "conv53-field-provenance-ledger-v1",
        "family": FAMILY,
        "allowed_origins": sorted(ORIGIN_ENUM),
        "target_schema_surface": {
            "pointer_count_per_stage": len(target_pointers),
            "pointer_source": (
                "union of pinned upstream SA JSON surface and current node0004 "
                "serialized/native comparison surfaces; values are not inherited"
            ),
            "pointers": target_pointers,
        },
        "coverage": {
            "stage_count": len(stages),
            "ledger_entry_count": len(stages) * len(target_pointers),
            "complete_stage_ledger_count": len(records),
            "unresolved_or_unknown_count": unresolved_count,
            "source_absent_not_applicable_count": not_applicable_count,
            "status_counts": dict(sorted(per_pointer_counts.items())),
        },
        "materialization_gate": {
            "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
            "strict_complete_json_materialized_count": 0,
            "reason": (
                "every target has SOURCE_ABSENT_UNKNOWN_FOR_TARGET physical leaves"
            ),
        },
        "stages": records,
    }


def build_current_diff(
    project_root: Path,
    stages: list[dict[str, Any]],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    serialized = load_json(project_root / SERIALIZED_CONFIG_REL)
    native = load_json(project_root / NATIVE_CONFIG_REL)
    serialized_leaves = flatten_json(serialized)
    native_leaves = flatten_json(native)
    target_entries = {
        item["json_pointer"]: item
        for item in next(
            item
            for item in ledger["stages"]
            if item["hw_op_id"] == "hwop-0004-00"
        )["entries"]
    }
    physical_diff: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    for pointer in sorted(set(serialized_leaves) | set(native_leaves)):
        serial_present = pointer in serialized_leaves
        native_present = pointer in native_leaves
        serial_value = serialized_leaves.get(pointer)
        native_value = native_leaves.get(pointer)
        relation = (
            "same"
            if serial_present and native_present and serial_value == native_value
            else "route_specific_difference"
            if serial_present and native_present
            else "serialized_only"
            if serial_present
            else "native_only"
        )
        target = target_entries.get(pointer)
        if target and target["status"] == "SOURCE_ABSENT_NOT_APPLICABLE":
            category = "intentional_derivation"
        elif relation == "route_specific_difference":
            category = "intentional_derivation"
        else:
            category = "dynamic-only"
        category_counts[category] += 1
        relation_counts[relation] += 1
        physical_diff.append(
            {
                "json_pointer": pointer,
                "serialized_current": {
                    "present": serial_present,
                    "value": serial_value,
                },
                "native_four_lane_current": {
                    "present": native_present,
                    "value": native_value,
                },
                "new_candidate": {
                    "materialized": False,
                    "status": target["status"] if target else "UNRESOLVED",
                    "value": None,
                },
                "current_route_relation": relation,
                "classification": category,
                "explanation": (
                    "route-specific schedule/topology leaf is not transferable"
                    if category == "intentional_derivation"
                    else "candidate physical owner/equation is unresolved; server "
                    "dynamic behavior cannot establish target provenance"
                ),
            }
        )

    node4 = next(
        stage for stage in stages if stage["identity"]["hw_op_id"] == "hwop-0004-00"
    )
    logical_diff = [
        {
            "field": "op",
            "new_lowering_value": node4["op"],
            "serialized_current_value": "ConvInt32Accumulate",
            "native_current_value": "ConvInt32Accumulate",
            "classification": "same",
        },
        {
            "field": "dtype",
            "new_lowering_value": node4["dtype"],
            "serialized_current_value": node4["dtype"],
            "native_current_value": node4["dtype"],
            "classification": "same",
        },
        {
            "field": "shape",
            "new_lowering_value": node4["shape"],
            "serialized_current_value": node4["shape"],
            "native_current_value": node4["shape"],
            "classification": "same",
        },
        {
            "field": "padding_tail",
            "new_lowering_value": node4["padding_tail"],
            "serialized_current_value": node4["padding_tail"],
            "native_current_value": node4["padding_tail"],
            "classification": "same",
        },
        {
            "field": "qparams",
            "new_lowering_value": node4["qparams"],
            "serialized_current_value": node4["qparams"],
            "native_current_value": node4["qparams"],
            "classification": "same",
        },
    ]
    for item in logical_diff:
        category_counts[item["classification"]] += 1

    return {
        "schema": "conv53-current-test-diff-v1",
        "family": FAMILY,
        "comparison_scope": (
            "node0004 current serialized v48 and native four-lane p8f only; "
            "remaining 52 have no current materialized in-test configs"
        ),
        "source_receipts": {
            SERIALIZED_CONFIG_REL.as_posix(): sha256_file(
                project_root / SERIALIZED_CONFIG_REL
            ),
            NATIVE_CONFIG_REL.as_posix(): sha256_file(
                project_root / NATIVE_CONFIG_REL
            ),
            SERIALIZED_PACKAGE_REL.as_posix(): sha256_file(
                project_root / SERIALIZED_PACKAGE_REL
            ),
            NATIVE_PACKAGE_REL.as_posix(): sha256_file(
                project_root / NATIVE_PACKAGE_REL
            ),
        },
        "logical_leaf_comparison": logical_diff,
        "physical_leaf_comparison": physical_diff,
        "summary": {
            "category_counts": dict(sorted(category_counts.items())),
            "current_route_relation_counts": dict(sorted(relation_counts.items())),
            "suspected_current_defect_count": 0,
            "new_candidate_defect_count": 0,
        },
        "current_test_adjudication": {
            "serialized": {
                "current_identity": "r5_n4_hw_v48_lc9_actual",
                "status": "PACKAGE_READY_NOT_RUN_DIAGNOSTIC_ONLY",
                "last_formal_return": "v47",
                "compile_exit": 0,
                "run_exit": 0,
                "natural_terminal": False,
                "formal_d_expected": 320,
                "formal_d_present": 0,
                "formal_d_missing": 320,
                "current_stall_or_gap": (
                    "v47 observer was bound to non-actual LC9 consumers; v48 "
                    "corrects observer only and is not yet dynamically returned"
                ),
                "configuration_explains_current_gap": False,
            },
            "native_four_lane": {
                "current_identity": "r5_n4_0cc_p8f",
                "status": "PACKAGE_READY_NOT_RUN",
                "last_formal_return": "p7",
                "compile_exit": 0,
                "run_exit": 124,
                "qualified_progressing_windows": 28,
                "natural_terminal": False,
                "formal_d_present": 0,
                "current_stall_or_gap": (
                    "p7 wallclock budget expired while qualified counters were "
                    "still increasing; p8f full chain is pending"
                ),
                "configuration_explains_current_gap": False,
            },
        },
        "closed_config_issue": {
            "serialized_special_array_transout_last_index": {
                "old": 2,
                "current": 5,
                "status": "CLOSED_IN_CURRENT_CONFIG",
                "not_a_new_candidate_finding": True,
            }
        },
        "excluded_non_config_boundaries": [
            "serialized v47 package-local observer actual-consumer misbinding",
            "serialized v48 pending natural terminal and formal D320",
            "native p7 runner wallclock timeout while qualified progress continued",
            "native p8f pending natural terminal and formal D320",
            "old outbuffer occupancy claim INVALIDATED_NOT_RTL_BUG",
        ],
    }


def build_public_blocked_contract(
    project_root: Path,
    output: Path,
    stages: list[dict[str, Any]],
    detailed_ledger: dict[str, Any],
) -> dict[str, Path]:
    family = FAMILY
    exactness_axes = {
        "op": False,
        "dtype": False,
        "shape": False,
        "layout": False,
        "qparams": False,
        "topology": False,
        "address": False,
        "schedule": False,
        "consumer": False,
    }
    blueprint = nullify_json_leaves(
        load_json(project_root / SERIALIZED_CONFIG_REL)
    )
    blueprint_path = output / "blocked_candidate_blueprint.json"
    write_json(blueprint_path, blueprint)
    blueprint_sha = sha256_file(blueprint_path)
    blueprint_leaves = flatten_json(blueprint)
    detailed_stage = next(
        item
        for item in detailed_ledger["stages"]
        if item["hw_op_id"] == "hwop-0004-00"
    )
    source_by_pointer = {
        item["json_pointer"]: item["source"]
        for item in detailed_stage["entries"]
    }
    ledger_entries = []
    source_absences = []
    current_entries = []
    for pointer, value in sorted(blueprint_leaves.items()):
        source = source_by_pointer.get(pointer)
        ledger_entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": "UNRESOLVED",
                "applicability_class": "UNRESOLVED",
                "exactness_axes": exactness_axes,
                "owner": (
                    "missing generic ConvInt32Accumulate semantic materializer"
                ),
                "consumer_equation": consumer_equation(pointer),
                "derivation_receipt": None,
                "source": source,
                "negative_control_ids": [
                    "unresolved_leaf_with_implicit_zero",
                    "project_D_reference_promoted_to_exact",
                ],
                "status": "UNRESOLVED",
            }
        )
        source_absences.append(
            {
                "target_json_pointer": pointer,
                "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
                "reason": (
                    "No authorized generic Conv handler/materializer equation "
                    "binds this target leaf; reference values are inventory only."
                ),
                "owner": (
                    "Conv/SA integration materializer capability gap"
                ),
            }
        )
        current_entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": value,
                "current_value_present": False,
                "current_value": None,
                "classification": "CURRENT_ABSENT",
                "reason": (
                    "The blocked blueprint is not a strict materialized target "
                    "configuration and has no current-test identity."
                ),
                "evidence": [
                    "complete_json_manifest.json",
                    "current_test_diff.json",
                ],
            }
        )
    public_ledger = {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": family,
        "candidate_json_sha256": blueprint_sha,
        "entries": ledger_entries,
        "source_absences": source_absences,
        "claim_boundary": (
            "Machine-readable BLOCKED blueprint only. Every declared physical "
            "leaf is unresolved; this is not a strict complete target JSON."
        ),
    }
    public_ledger_path = output / "blocked_candidate_field_provenance_ledger.json"
    write_json(public_ledger_path, public_ledger)
    capability = {
        "schema": "operator_config_handler_capability_v1",
        "family": family,
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
                    "Pinned upstream and current ndp-sim contain no generic "
                    "QLinearConv/ConvInt32Accumulate handler/materializer."
                ),
            }
            for axis in (
                "exact_replay",
                "shape",
                "dtype",
                "qparam",
                "layout",
                "address",
                "cross_stage_schedule",
            )
        },
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": [
                    "shape",
                    "dtype",
                    "qparam",
                    "layout",
                    "address",
                    "cross_stage_schedule",
                ],
                "covered_by": "NONE",
                "status": "UNCOVERED",
            }
            for pointer in sorted(blueprint_leaves)
        ],
        "claim_boundary": (
            "Capability absence report; file/registry presence is not "
            "generalization authority."
        ),
    }
    capability_path = output / "blocked_candidate_handler_capability.json"
    write_json(capability_path, capability)
    public_diff = {
        "schema": "operator_config_current_test_diff_v1",
        "family": family,
        "candidate_json_sha256": blueprint_sha,
        "current_identity": {
            "available": False,
            "path": None,
            "sha256": None,
            "package_or_record": None,
            "latest_result": (
                "BLOCKED_BLUEPRINT_HAS_NO_STRICT_CURRENT_TEST_IDENTITY; detailed "
                "serialized/native comparison is in current_test_diff.json"
            ),
        },
        "entries": current_entries,
        "blocker_attribution": [
            {
                "blocker_id": "B_CONV53_GENERIC_MATERIALIZER_ABSENT",
                "classification": "INSUFFICIENT_EVIDENCE",
                "candidate_json_pointers": [],
                "reason": (
                    "No legal strict candidate exists, so current dynamic gaps "
                    "cannot be attributed to a newly generated configuration."
                ),
                "evidence": [
                    "handler_capability.json",
                    "field_provenance_ledger.json",
                    "current_test_diff.json",
                ],
            },
            {
                "blocker_id": "B_CONV_CURRENT_DYNAMIC_TERMINAL_AND_FORMAL_D",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": (
                    "Serialized v48 and native p8f natural terminal/formal D "
                    "remain pending and are not configuration provenance."
                ),
                "evidence": [
                    ".agents/task_records/20260805_conv_node0004_v47_return_v48_lc9_actual_successor.md",
                    ".agents/task_records/20260805_conv_native_four_lane_p7_return_p8f_full_successor.md",
                ],
            },
        ],
        "claim_boundary": (
            "Public-schema comparison for a BLOCKED blueprint; detailed current "
            "serialized/native leaf comparison is a separate read-only artifact."
        ),
    }
    public_diff_path = output / "blocked_candidate_current_test_diff.json"
    write_json(public_diff_path, public_diff)
    contract = {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": family,
        "candidate_status": "BLOCKED",
        "reference_class": "D",
        "changed_axes": [
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        ],
        "target_hw_op_types": ["ConvInt32Accumulate"],
        "stage_ids": [stage["identity"]["hw_op_id"] for stage in stages],
        "candidate_json": bound(project_root, blueprint_path),
        "field_provenance_ledger": bound(project_root, public_ledger_path),
        "handler_capability": bound(project_root, capability_path),
        "current_test_diff": bound(project_root, public_diff_path),
        "composition": {"required": False, "boundary": None},
        "artifact_root": output.relative_to(project_root).as_posix(),
        "claim_boundary": (
            "All 53 ConvInt32Accumulate lowering stages are enumerated exactly "
            "once, but no strict target JSON is emitted because required physical "
            "leaves and the generic materializer are unresolved."
        ),
    }
    contract_path = output / "blocked_candidate_contract.json"
    write_json(contract_path, contract)
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": family,
        "target_hw_op_types": ["ConvInt32Accumulate"],
        "candidate_contracts": [bound(project_root, contract_path)],
        "no_config_stages": [],
        "claim_boundary": (
            "All 53 ConvInt32Accumulate lowering stages occur exactly once in "
            "the BLOCKED candidate contract. Conv is not eligible for the "
            "View-only no_config_stages exception."
        ),
    }
    family_set_path = output / "family_set.json"
    write_json(family_set_path, family_set)
    return {
        "blueprint": blueprint_path,
        "ledger": public_ledger_path,
        "handler": capability_path,
        "diff": public_diff_path,
        "contract": contract_path,
        "family_set": family_set_path,
    }


def source_receipts(project_root: Path) -> dict[str, dict[str, Any]]:
    paths = [
        *PROJECT_RULE_RELS,
        LOWERING_REL,
        LIFETIME_REL,
        EXPANSION_REL,
        SERIALIZED_CONFIG_REL,
        NATIVE_CONFIG_REL,
        SERIALIZED_PACKAGE_REL,
        NATIVE_PACKAGE_REL,
    ]
    result: dict[str, dict[str, Any]] = {}
    for relative in paths:
        full = project_root / relative
        result[relative.as_posix()] = {
            "bytes": full.stat().st_size,
            "sha256": sha256_file(full),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else (root / OUTPUT_REL).resolve()
    )
    output.mkdir(parents=True, exist_ok=True)
    complete_json_dir = output / "complete_json"
    complete_json_dir.mkdir(parents=True, exist_ok=True)
    if any(complete_json_dir.iterdir()):
        raise ValueError(
            "complete_json must be empty for fail-closed regeneration; "
            "refusing to overwrite existing candidates"
        )

    lowering = load_json(root / LOWERING_REL)
    lifetime = load_json(root / LIFETIME_REL)
    stages, equivalence_classes = build_stage_catalog(lowering, lifetime)
    reference_report, reference_state = build_references(root)
    capability = build_capability_matrix(root, reference_state)
    ledger = build_leaf_ledger(root, stages, reference_state)
    current_diff = build_current_diff(root, stages, ledger)
    public_contract_paths = build_public_blocked_contract(
        root, output, stages, ledger
    )
    receipts = source_receipts(root)

    write_json(output / "stage_catalog.json", {"stages": stages})
    write_json(
        output / "equivalence_classes.json",
        {
            "schema": "conv53-materialized-consumer-signatures-v1",
            "class_count": len(equivalence_classes),
            "classes": equivalence_classes,
        },
    )
    write_json(output / "reference_applicability.json", reference_report)
    write_json(output / "handler_capability.json", capability)
    write_json(output / "field_provenance_ledger.json", ledger)
    write_json(output / "current_test_diff.json", current_diff)
    write_json(
        output / "complete_json_manifest.json",
        {
            "schema": "conv53-strict-complete-json-materialization-manifest-v1",
            "family": FAMILY,
            "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
            "target_stage_count": 53,
            "materialized_complete_json_count": 0,
            "complete_json_directory": "complete_json",
            "directory_expected_empty": True,
            "unresolved_or_unknown_leaf_count": ledger["coverage"][
                "unresolved_or_unknown_count"
            ],
            "first_missing_capability": (
                "pinned upstream and current ndp-sim lack a generic "
                "QLinearConv/ConvInt32Accumulate handler/materializer; physical "
                "layout/address/lifetime/cross-stage schedule equations are absent"
            ),
            "no_value_inherited_from_current_test_config": True,
        },
    )
    report = {
        "schema": "conv53-complete-json-regeneration-report-v1",
        "family": FAMILY,
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "source_receipts": receipts,
        "coverage": {
            "target_stage_count": len(stages),
            "materialized_consumer_signature_count": len(equivalence_classes),
            "strict_complete_json_materialized_count": 0,
            "ledger_entry_count": ledger["coverage"]["ledger_entry_count"],
            "unresolved_or_unknown_leaf_count": ledger["coverage"][
                "unresolved_or_unknown_count"
            ],
            "source_absent_not_applicable_count": ledger["coverage"][
                "source_absent_not_applicable_count"
            ],
            "public_family_set_stage_ids": 53,
        },
        "capability_conclusion": {
            "exact_upstream_conv_template_count": 0,
            "generic_conv_handler_present": False,
            "generic_conv_materializer_present": False,
            "mapper_encoder_can_fill_semantic_leaves": False,
            "materialization_allowed": False,
            "precise_blocked_leaf_families": [
                "CONFIG topology enable",
                "DRAM LC start/end/stride/last_index chain",
                "LC-PE source/mode/keep",
                "buffer row/column loops",
                "buffer mode/mask/capacity/lifetime",
                "MSE target/base/index/stride/padding/tail/pingpong",
                "N2N routing",
                "SA inport/outport pingpong and terminal threshold",
                "physical allocation/address/bank/row",
                "cross-stage visibility/barrier/release",
            ],
        },
        "current_test_findings": {
            "suspected_current_config_defect_count": 0,
            "new_candidate_defect_count": 0,
            "current_stalls_explained_by_new_config_diff": False,
            "reason": (
                "no candidate physical JSON was legal to materialize; current "
                "serialized v47 gap is observer binding, native p7 is progressing "
                "wallclock expiry, and both full dynamic terminal/D gates remain open"
            ),
        },
        "claim_boundary": {
            "logical_stage_inventory": "COMPLETE_53_OF_53",
            "signature_inventory": "COMPLETE",
            "field_provenance_ledger": "COMPLETE_FOR_DECLARED_STRICT_SURFACE",
            "strict_json": "NOT_MATERIALIZED_FAIL_CLOSED",
            "mapping_bitstream_execplan_sca": "NOT_GENERATED",
            "numeric_w3_golden_repeated": False,
            "server_package_generated_or_modified": False,
            "server_action": False,
            "functional_rtl_modified": False,
            "plan_or_public_rules_modified": False,
            "counts_as_e2_e3_e4_e5": False,
        },
        "rule_feedback": {
            "type": "RULE_DELTA_PROPOSAL",
            "confirmed_existing_intent": (
                "CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001, "
                "CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001, strict completeness, "
                "semantic ownership and current materialized-consumer rules are "
                "sufficient to force fail-closed rather than nearest-template fill."
            ),
            "rule_delta_proposal": [
                {
                    "proposal_id": (
                        "CDA-COMPLETE-JSON-BLOCKED-CANDIDATE-FAMILY-COVERAGE-001"
                    ),
                    "problem": (
                        "The common candidate validator appends 'BLOCKED candidate "
                        "did not expose...' whenever a BLOCKED contract has no prior "
                        "schema error, without testing its UNRESOLVED ledger count, "
                        "NONE/unsupported handler axes, uncovered dependent leaves, "
                        "or unresolved composition. It also defines pass=true only "
                        "for COMPLETE, while the family auditor requires pass=true "
                        "for every contract. A structurally valid BLOCKED whole-family "
                        "contract therefore cannot be represented as valid coverage."
                    ),
                    "executable_change": (
                        "Return separate contract_valid and candidate_complete flags. "
                        "For BLOCKED, require at least one machine-detectable blocker "
                        "(UNRESOLVED leaf/absence, unsupported or uncovered handler "
                        "dependency, or unresolved composition), set contract_valid="
                        "true and candidate_complete=false. Family-set coverage shall "
                        "accept contract_valid for exact-once accounting while keeping "
                        "family_complete=false and release blocked."
                    ),
                    "negative_controls": [
                        "BLOCKED with zero unresolved/unsupported/uncovered must fail",
                        "BLOCKED with stage type outside target_hw_op_types must fail",
                        "BLOCKED stage duplicated across contracts must fail",
                        "Conv in no_config_stages must fail",
                    ],
                }
            ],
        },
        "public_gate_integration": {
            "target_hw_op_types": ["ConvInt32Accumulate"],
            "candidate_status": "BLOCKED",
            "candidate_contract": bound(root, public_contract_paths["contract"]),
            "family_set": bound(root, public_contract_paths["family_set"]),
            "expected_candidate_validator_exit": 1,
            "expected_family_set_auditor_exit": 1,
            "expected_reason": (
                "all 53 stages are listed exactly once, but BLOCKED candidates "
                "cannot satisfy complete-JSON family release"
            ),
        },
    }
    write_json(output / "report.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
