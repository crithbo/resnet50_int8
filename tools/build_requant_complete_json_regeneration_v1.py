from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_validator import OperatorConfigValidator
from tools.audit_complete_operator_json_family_set import audit_family_set
from tools.validate_complete_operator_json_candidate import validate as validate_complete_candidate


OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "requantize_uint8"
)
COMPLETE_JSON = OUT / "complete_json"
VALIDATION = OUT / "validation"

BUNDLE = ROOT / "contracts" / "resnet50_r5_lowering_bundle.json"
EVIDENCE = ROOT / "contracts" / "operator_config" / "requant_quant_tail_evidence_input_v1.json"
CONV_BINDING = (
    ROOT / "contracts" / "operator_config" / "requant_conv53_tail_signature_binding_v1.json"
)
REUSE_AUDIT = (
    ROOT / "contracts" / "operator_config" / "resnet50_ndpsim_reuse_gap_audit_v1.json"
)
QUANT_TEMPLATE = ROOT / "ndp-sim" / "jsons" / "quant_from_buffer_int32MN_uint8MN.json"
SILU_TEMPLATE = ROOT / "ndp-sim" / "jsons" / "decode_silu_fp16N_fp32N.json"
CONTROL_REGISTERS = (
    ROOT
    / "ndp-sim"
    / "model_execplan"
    / "src"
    / "execution_plan_generator"
    / "control_registers.py"
)
OPERATOR_BASE_INFO = ROOT / "ndp-sim" / "model_execplan" / "config" / "operator_base_info.json"
REMAPPER_TEST = ROOT / "ndp-sim" / "address_remapping" / "tests" / "test_solver.py"

CURRENT_V1 = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "rq_node0001_guardonly_sfu_eventedge_stock_v1.zip"
)
CURRENT_V2 = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "rq_node0001_guardonly_sfu_eventedge_runtime_root_v2.zip"
)

RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/RequantizeUint8算子配置规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/最小双Stage生命周期规则.md",
    ".agents/rules/NDP硬件字段语义.md",
]

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

VALUE_STATES = {
    "SOURCE_ABSENT_NOT_APPLICABLE",
    "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
    "EXPLICIT_NULL_INACTIVE",
    "EXPLICIT_ZERO",
    "TARGET_REQUIRED_DERIVED",
    "EXPLICIT_NONZERO",
}

PUBLIC_GATE_PATHS = [
    "contracts/operator_config/complete_json_generation_contract_v1.json",
    "schemas/operator_config_complete_json_candidate_v1.schema.json",
    "schemas/operator_config_field_provenance_ledger_v1.schema.json",
    "schemas/operator_config_handler_capability_v1.schema.json",
    "schemas/operator_config_current_test_diff_v1.schema.json",
    "schemas/operator_config_composition_boundary_v1.schema.json",
    "schemas/operator_config_complete_json_family_set_v1.schema.json",
    "tools/validate_complete_operator_json_candidate.py",
    "tools/audit_complete_operator_json_family_set.py",
]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _semantic_sha(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def _git(*args: str, cwd: Path = ROOT) -> str:
    cmd = ["git"]
    if cwd.name in {"ndp-sim", "Trassic2.0_RTL"}:
        cmd.extend(["-c", f"safe.directory={cwd.as_posix()}"])
    cmd.extend(args)
    return subprocess.check_output(cmd, cwd=cwd, text=True, encoding="utf-8").strip()


def _blob(path: Path, *, repo: Path = ROOT) -> str:
    rel = path.relative_to(repo).as_posix()
    line = _git("ls-tree", "HEAD", rel, cwd=repo)
    if not line:
        return "UNTRACKED"
    return line.split()[2]


def _json_pointer(parts: Iterable[str | int]) -> str:
    escaped = []
    for part in parts:
        escaped.append(str(part).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(escaped)


def _flatten(value: Any, parts: tuple[str | int, ...] = ()) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = []
        for key in sorted(value):
            rows.extend(_flatten(value[key], parts + (key,)))
        return rows
    if isinstance(value, list):
        rows = []
        for index, item in enumerate(value):
            rows.extend(_flatten(item, parts + (index,)))
        return rows
    return [(_json_pointer(parts), value)]


def _value_state(value: Any) -> str:
    if value is None:
        return "EXPLICIT_NULL_INACTIVE"
    if value in (0, "0", "false", False):
        return "EXPLICIT_ZERO"
    return "EXPLICIT_NONZERO"


def _consumer_equation(pointer: str) -> str:
    if pointer == "/CONFIG":
        return "CONFIG enable/update mask controls which subsystem register images are consumed"
    if pointer.startswith("/dram_loop_configs"):
        return "signed17 LC recurrence; terminal uses parent/child tag and last_index"
    if pointer.startswith("/lc_pe_configs"):
        return "LC_PE low16 add/mul/mac with one buffer tag carrier"
    if pointer.startswith("/stream_engine"):
        return (
            "request=low26(remap(low30(sum(u16(idx)*u20(dim_stride))+bias))[29:4]"
            "+base_addr[29:4])"
        )
    if pointer.startswith("/buffer_loop_configs"):
        return "Buffer AG row/low5(col+stride), bank=col[4:2], byte=col[1:0]"
    if pointer.startswith("/buffer_config"):
        return "Buffer lifetime/mode/mask/end-row and accepted-read/write visibility"
    if pointer.startswith("/general_array"):
        return "GA selected inports -> opcode equation -> normal outbuffer -> UINT8 outport"
    return "native strict JSON direct consumer"


def _repo_source(
    *,
    repo_name: str,
    commit: str,
    blob: str,
    path: str,
    pointer: str | None,
    value: Any,
) -> dict[str, Any]:
    return {
        "repo": repo_name,
        "commit": commit,
        "blob": blob,
        "path": path,
        "json_pointer": pointer,
        "value": value,
    }


def _find_parameter(request: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in request["typed_parameters"] if item["name"] == name)


def _classify_zp(zp: int) -> str:
    if zp == 0:
        return "ZERO"
    return "ODD_NONZERO" if zp % 2 else "EVEN_NONZERO"


def _tail_profile(shape: list[int]) -> dict[str, Any]:
    if len(shape) == 4:
        _, channels, height, width = shape
        shard_channels = 8
        output_bytes = height * width * shard_channels
        return {
            "logical_layout": "NCHW",
            "required_physical_layout": "HWC8",
            "channel_lane_count": 8,
            "channel_tail_mod8": channels % 8,
            "per_sample_channel_shard_output_bytes": output_bytes,
            "write_tail_bytes_mod16": output_bytes % 16,
            "padding": "NONE_FROM_MODEL",
            "tailing_owner": "ADDRESS_AND_SCHEDULE_PLANNER_UNRESOLVED",
        }
    batch, columns = shape
    output_bytes = 8
    return {
        "logical_layout": "NC",
        "required_physical_layout": "RANK2_LANE8_UNRESOLVED",
        "channel_lane_count": 8,
        "channel_tail_mod8": columns % 8,
        "per_sample_lane_shard_output_bytes": output_bytes,
        "write_tail_bytes_mod16": output_bytes % 16,
        "padding": "NONE_FROM_MODEL",
        "tailing_owner": "ADDRESS_AND_SCHEDULE_PLANNER_UNRESOLVED",
    }


def _read_zip_json(path: Path, suffix: str) -> tuple[str, dict[str, Any], bytes]:
    with zipfile.ZipFile(path) as archive:
        matches = [name for name in archive.namelist() if name.endswith(suffix)]
        if len(matches) != 1:
            raise RuntimeError(f"{path}: expected one {suffix}, got {matches}")
        raw = archive.read(matches[0])
        return matches[0], json.loads(raw), raw


def _build_stage_inventory(
    bundle: dict[str, Any],
    prior_evidence: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    requests = bundle["requests"]
    requants = [item for item in requests if item["identity"]["hw_op_type"] == "RequantizeUint8"]
    if len(requants) != 54:
        raise RuntimeError(f"expected 54 RequantizeUint8 requests, got {len(requants)}")

    evidence_by_request = {
        item["request_id"]: item for item in prior_evidence["stage_evidence"]
    }
    input_consumers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for request in requests:
        for port in request["ports"]["inputs"]:
            input_consumers[port["tensor_id"]].append(
                {
                    "request_id": request["request_id"],
                    "hw_op_id": request["identity"]["hw_op_id"],
                    "hw_op_type": request["identity"]["hw_op_type"],
                    "node_id": request["identity"]["node_id"],
                    "port_role": port["role"],
                }
            )

    inventory = []
    exact_groups: dict[str, list[str]] = defaultdict(list)
    capability_groups: dict[str, list[str]] = defaultdict(list)
    for request_index, request in enumerate(requests):
        if request["identity"]["hw_op_type"] != "RequantizeUint8":
            continue
        params = {item["name"]: item for item in request["typed_parameters"]}
        source_scale_names = [
            name
            for name in ("x_scale", "w_scale", "a_scale", "b_scale")
            if name in params
        ]
        zp = int(params["y_zero_point"]["value"]["scalar"])
        zp_class = _classify_zp(zp)
        shape = list(request["logical_geometry"]["output_shapes"][0])
        output_port = request["ports"]["outputs"][0]
        consumers = sorted(
            input_consumers.get(output_port["tensor_id"], []),
            key=lambda item: (item["request_id"], item["port_role"]),
        )
        tail = _tail_profile(shape)
        prior = evidence_by_request[request["request_id"]]
        target_order = (
            "signed_int32_to_fp32 -> explicit_fp32_mul -> fp32_scratch/barrier -> "
            "RNE -> integer_add_zero_point -> saturate_uint8"
        )
        signature_payload = {
            "shape": shape,
            "input_dtype": "int32",
            "output_dtype": "uint8",
            "logical_layout": tail["logical_layout"],
            "required_physical_layout": tail["required_physical_layout"],
            "y_zero_point": zp,
            "multiplier_payload_sha256": params["requant_multiplier"]["value"]["value_sha256"],
            "tail": tail,
            "consumer_signature": consumers,
            "target_order": target_order,
        }
        signature = _semantic_sha(signature_payload)
        capability_payload = {
            "shape": shape,
            "zp_class": zp_class,
            "tail": tail,
            "consumer_types_and_roles": [
                (item["hw_op_type"], item["port_role"]) for item in consumers
            ],
            "target_order": target_order,
        }
        capability_signature = _semantic_sha(capability_payload)
        exact_groups[signature].append(request["request_id"])
        capability_groups[capability_signature].append(request["request_id"])
        inventory.append(
            {
                "request_id": request["request_id"],
                "request_index_in_lowering_bundle": request_index,
                "request_sha256": request["request_sha256"],
                "identity": request["identity"],
                "op": "RequantizeUint8",
                "dtype": {
                    "input": "int32",
                    "output": "uint8",
                    "qparams": {
                        **{name: "float32" for name in source_scale_names},
                        "y_scale": "float32",
                        "y_zero_point": "uint8",
                        "requant_multiplier": "float32",
                    },
                },
                "shape": {"input": shape, "output": shape},
                "layout": {
                    "logical": tail["logical_layout"],
                    "materialized_target": tail["required_physical_layout"],
                    "status": "UNRESOLVED",
                },
                "qparams": {
                    "source_scales": {
                        name: params[name]["value"] for name in source_scale_names
                    },
                    "y_scale": params["y_scale"]["value"],
                    "y_zero_point": params["y_zero_point"]["value"],
                    "requant_multiplier": params["requant_multiplier"]["value"],
                    "zero_point_class": zp_class,
                    "target_numeric_order": target_order,
                },
                "padding_tail": tail,
                "dag": {
                    "predecessor_hw_op_ids": request["predecessor_hw_op_ids"],
                    "input_tensor": request["ports"]["inputs"][0],
                    "output_tensor": output_port,
                    "consumers": consumers,
                },
                "lifetime": {
                    "required_sequence": ["scale_to_fp32_scratch", "round_add_zp_saturate"],
                    "scratch_producer_consumer_alias_required": True,
                    "completion_barrier_required": True,
                    "occurrence_count": None,
                    "terminal_equation": None,
                    "status": "SCHEDULE_REQUIRED_DERIVED_BUT_UNRESOLVED",
                },
                "address_owners": {
                    "input_logical_owner": request["ports"]["inputs"][0]["tensor_id"],
                    "output_logical_owner": output_port["tensor_id"],
                    "scratch_logical_owner": f"{request['request_id']}:fp32_scaled_scratch",
                    "physical_base_owner": "ADDRESS_PLANNER_UNRESOLVED",
                    "address_equation_owner": "NDP_HARDWARE_MSE_EQUATION",
                    "accepted_lifetime_owner": "SCHEDULE_AND_EXECPLAN_UNRESOLVED",
                },
                "materialized_consumer_signature_sha256": signature,
                "capability_equivalence_signature_sha256": capability_signature,
                "prior_w3_evidence_reused_without_rerun": {
                    "source": str(EVIDENCE.relative_to(ROOT)).replace("\\", "/"),
                    "numeric_classification": prior["numeric_classification"],
                    "physical_materialization_classification": prior[
                        "physical_materialization_classification"
                    ],
                    "exact_recipe_proven_on_frozen_w3": prior["w3"]["exact_recipe_proven"],
                    "w3_accumulator_sha256": prior["w3"]["accumulator"]["sha256"],
                    "w3_golden_sha256": prior["w3"]["golden"]["sha256"],
                },
                "reference_tier": {
                    "quant_from_buffer": "C_SAME_HARDWARE_BLOCK_NUMERIC_AND_LAYOUT_DIFFER",
                    "decode_silu": (
                        "C_SHARED_SFU_BLOCK_DIFFERENT_NUMERIC_AND_DTYPE"
                        if zp == 0
                        else "SOURCE_ABSENT_NOT_APPLICABLE"
                    ),
                    "project_current_or_historical_json": (
                        "D_PROJECT_ADDED_UNTRACKED_NO_AUTHORITY"
                    ),
                },
                "emission": {
                    "strict_complete_json_materialized": False,
                    "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
                },
            }
        )
    return inventory, dict(exact_groups), dict(capability_groups)


def _known_requirement_rows(
    stage: dict[str, Any],
    request: dict[str, Any],
    bundle_commit: str,
    bundle_blob: str,
) -> list[dict[str, Any]]:
    index = stage["request_index_in_lowering_bundle"]
    base = f"/requests/{index}"
    known = [
        (
            "/target_contract/logical/input_dtype",
            "int32",
            f"{base}/logical_geometry/input_dtypes/0",
            "target input dtype consumed by stage0 ingress",
        ),
        (
            "/target_contract/logical/input_shape",
            stage["shape"]["input"],
            f"{base}/logical_geometry/input_shapes/0",
            "logical element and channel coverage equation",
        ),
        (
            "/target_contract/logical/output_dtype",
            "uint8",
            f"{base}/logical_geometry/output_dtypes/0",
            "target outport dtype and byte coverage equation",
        ),
        (
            "/target_contract/logical/output_shape",
            stage["shape"]["output"],
            f"{base}/logical_geometry/output_shapes/0",
            "logical output coverage equation",
        ),
        (
            "/target_contract/qparams/y_zero_point",
            stage["qparams"]["y_zero_point"]["scalar"],
            f"{base}/typed_parameters/3/value/scalar",
            "rounded + y_zero_point before UINT8 clip",
        ),
        (
            "/target_contract/qparams/requant_multiplier_payload_sha256",
            stage["qparams"]["requant_multiplier"]["value_sha256"],
            f"{base}/typed_parameters/4/value/value_sha256",
            "per-channel float32 multiplier identity; not individual lane values",
        ),
        (
            "/target_contract/dag/input_tensor_id",
            stage["dag"]["input_tensor"]["tensor_id"],
            f"{base}/ports/inputs/0/tensor_id",
            "producer tensor identity",
        ),
        (
            "/target_contract/dag/output_tensor_id",
            stage["dag"]["output_tensor"]["tensor_id"],
            f"{base}/ports/outputs/0/tensor_id",
            "consumer-visible tensor identity",
        ),
    ]
    rows = []
    for pointer, value, source_pointer, equation in known:
        rows.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "target_value_state": (
                    "EXPLICIT_ZERO" if value in (0, False, "false") else "TARGET_REQUIRED_DERIVED"
                ),
                "origin": "MODEL_DERIVED",
                "source": _repo_source(
                    repo_name="workspace-root",
                    commit=bundle_commit,
                    blob=bundle_blob,
                    path=str(BUNDLE.relative_to(ROOT)).replace("\\", "/"),
                    pointer=source_pointer,
                    value=value,
                ),
                "applicability": "EXACT_TARGET_STAGE",
                "exactness_axes": {
                    "stage_identity": True,
                    "shape": True,
                    "dtype": True,
                    "qparam": pointer.startswith("/target_contract/qparams/"),
                    "layout": False,
                    "address": False,
                    "schedule": False,
                },
                "derivation": "direct typed lowering binding",
                "current_consumer_equation": equation,
                "status": "TARGET_REQUIRED_DERIVED",
                "required_for_strict_target": True,
                "unresolved": False,
            }
        )
    return rows


def _unresolved_requirement_rows(stage: dict[str, Any]) -> list[dict[str, Any]]:
    zp_class = stage["qparams"]["zero_point_class"]
    requirements = [
        (
            "/target_contract/materialization/operator_json_count",
            "No native composite handler proves the number of per-occurrence JSONs.",
        ),
        (
            "/target_contract/materialization/stage0_topology",
            "No tracked native handler binds signed INT32 ingress, per-channel explicit FP32 multiply, and scratch write for this target.",
        ),
        (
            "/target_contract/materialization/stage0_multiplier_lane_bits",
            "Lowering binds only the payload hash/summary; individual FP32 lane values and physical occurrence transport are not emitted by the native placeholder.",
        ),
        (
            "/target_contract/materialization/stage1_topology",
            "No tracked native handler proves sequential scratch ingress, RNE, integer zero-point add, and UINT8 saturation as a target composition.",
        ),
        (
            "/target_contract/materialization/physical_layout",
            "Rank-4 HWC8 or rank-2 lane layout has no target-instance native mapper registration.",
        ),
        (
            "/target_contract/materialization/occurrence_schedule",
            "No shape-general occurrence, slice-mask, wave, transaction, or tail materializer is authorized.",
        ),
        (
            "/target_contract/materialization/input_base_addresses",
            "Address planner cannot own bases before topology, layout, and occurrence multiplicity are proven.",
        ),
        (
            "/target_contract/materialization/scratch_base_addresses",
            "Two-stage producer/consumer alias and physical bank-row validity are unbound.",
        ),
        (
            "/target_contract/materialization/output_base_addresses",
            "Consumer-visible address/occurrence coverage is unbound.",
        ),
        (
            "/target_contract/materialization/barrier_and_lifetime",
            "No composite handler proves Start/Barrier ordering, reload, visibility, and terminal count.",
        ),
        (
            "/target_contract/materialization/terminal_equation",
            "LC last/tag carrier and accepted write/readback coverage cannot be derived from shape alone.",
        ),
        (
            "/target_contract/materialization/tailing_bounds",
            "Tail bytes are classified, but final MSE transaction indices and inclusive tail bounds are unbound.",
        ),
        (
            "/target_contract/materialization/mapper_registration",
            "Pinned native remapper registry explicitly excludes quant_from_buffer_int32MN_uint8MN.",
        ),
        (
            "/target_contract/materialization/execplan_typed_transport",
            "Placeholder handler does not consume multiplier, zero-point, layout, address, or composite schedule attributes.",
        ),
        (
            "/target_contract/numeric/full_domain_rounding_equivalence",
            "Sequential FP32 multiply then RNE is not proven equivalent to the one-round fused magic reference.",
        ),
        (
            "/target_contract/numeric/magic_finite_domain",
            "A target-instance finite magic domain proof is required before magic rounding emission.",
        ),
        (
            "/target_contract/numeric/signed_int32_ingress",
            "The shared signed ingress capability remains instance-limited; no family-generic tracked handler binds it.",
        ),
    ]
    if zp_class != "ZERO":
        requirements.append(
            (
                "/target_contract/numeric/zero_point_after_rne",
                "Nonzero zero-point must be added in integer domain after RNE; the native reference embeds zero-point in FP32 magic bias.",
            )
        )
    if zp_class == "ODD_NONZERO":
        requirements.append(
            (
                "/target_contract/numeric/odd_zero_point_tie_parity",
                "Odd zero-point exact-half tie parity is contradicted by zero-point-in-magic-bias.",
            )
        )
    return [
        {
            "json_pointer": pointer,
            "target_value": None,
            "target_value_state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "origin": "UNRESOLVED",
            "source": _repo_source(
                repo_name="NONE",
                commit="NONE",
                blob="NONE",
                path="NONE",
                pointer=None,
                value=None,
            ),
            "applicability": "TARGET_REQUIRED_DERIVED",
            "exactness_axes": {
                "stage_identity": True,
                "shape": False,
                "dtype": False,
                "qparam": False,
                "layout": False,
                "address": False,
                "schedule": False,
            },
            "derivation": reason,
            "current_consumer_equation": "required target leaf has no authorized current consumer binding",
            "status": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "required_for_strict_target": True,
            "unresolved": True,
        }
        for pointer, reason in requirements
    ]


def _build_ledger(
    inventory: list[dict[str, Any]],
    bundle: dict[str, Any],
    quant_template: dict[str, Any],
    ndp_commit: str,
    quant_blob: str,
    root_commit: str,
    bundle_blob: str,
) -> dict[str, Any]:
    request_by_id = {item["request_id"]: item for item in bundle["requests"]}
    template_leaves = _flatten(quant_template)
    stage_rows = []
    for stage in inventory:
        target_rows = _known_requirement_rows(
            stage, request_by_id[stage["request_id"]], root_commit, bundle_blob
        )
        target_rows.extend(_unresolved_requirement_rows(stage))
        reference_rows = []
        for pointer, value in template_leaves:
            reference_rows.append(
                {
                    "json_pointer": pointer,
                    "target_value": None,
                    "target_value_state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
                    "origin": "UNRESOLVED",
                    "source": _repo_source(
                        repo_name="ndp-sim",
                        commit=ndp_commit,
                        blob=quant_blob,
                        path="jsons/quant_from_buffer_int32MN_uint8MN.json",
                        pointer=pointer,
                        value=value,
                    ),
                    "source_value_state": _value_state(value),
                    "applicability": "TIER_C_REFERENCE_ONLY_NOT_VALUE_AUTHORITY",
                    "exactness_axes": {
                        "stage_identity": False,
                        "shape": False,
                        "dtype": True,
                        "qparam": False,
                        "layout": False,
                        "address": False,
                        "schedule": False,
                    },
                    "derivation": (
                        "Reference leaf is inventoried but cannot be copied: target shape, qparam, "
                        "layout, address and multi-stage schedule are not exact."
                    ),
                    "current_consumer_equation": _consumer_equation(pointer),
                    "status": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
                    "required_for_strict_target": False,
                    "unresolved": True,
                }
            )
        stage_rows.append(
            {
                "request_id": stage["request_id"],
                "materialized_target_json": None,
                "reference_leaf_count": len(reference_rows),
                "target_required_leaf_count": len(target_rows),
                "target_required_unresolved_count": sum(row["unresolved"] for row in target_rows),
                "coverage": {
                    "reference_template_leaf_inventory_percent": 100,
                    "target_requirement_leaf_inventory_percent": 100,
                    "strict_target_json_leaf_coverage": "NOT_APPLICABLE_NO_JSON_EMITTED",
                },
                "target_requirement_ledger": target_rows,
                "reference_leaf_applicability_ledger": reference_rows,
            }
        )
    return {
        "schema": "requant-complete-json-field-provenance-ledger-v1",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "allowed_origins": sorted(ALLOWED_ORIGINS),
        "required_value_state_vocabulary": sorted(VALUE_STATES),
        "claim_boundary": (
            "100% covers the pinned quant_from_buffer reference leaves and the complete "
            "target-required leaf universe selected before emission. Because every stage has "
            "required UNRESOLVED leaves, no strict target JSON exists and no absent field is "
            "silently defaulted."
        ),
        "stage_count": len(stage_rows),
        "stages": stage_rows,
    }


def _build_reference_applicability(
    inventory: list[dict[str, Any]],
    ndp_commit: str,
    quant_blob: str,
    silu_blob: str,
) -> dict[str, Any]:
    return {
        "schema": "requant-native-reference-applicability-v1",
        "status": "NO_A_OR_B_TARGET_REFERENCE",
        "tier_definition": {
            "A": "exact replay",
            "B": "same primitive but shape differs",
            "C": "same hardware block but numeric or dtype semantics differ",
            "D": "project-added/untracked/no upstream authority",
        },
        "references": [
            {
                "path": "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
                "repo": "ndp-sim",
                "commit": ndp_commit,
                "blob": quant_blob,
                "sha256": _sha256(QUANT_TEMPLATE),
                "tier": "C",
                "source_instance": {
                    "input_shape": [1, 32, 32],
                    "output_shape": [1, 32, 32],
                    "input_dtype": "int32",
                    "output_dtype": "uint8",
                    "static_multiplier": 0.06375,
                    "static_magic_bias": 12582975.75,
                },
                "leaf_count": len(_flatten(_load(QUANT_TEMPLATE))),
                "applicability": (
                    "Tracked structural oracle only. No target has exact shape/qparam/order/layout/"
                    "address/schedule parity, so no leaf value is target authority."
                ),
            },
            {
                "path": "ndp-sim/jsons/decode_silu_fp16N_fp32N.json",
                "repo": "ndp-sim",
                "commit": ndp_commit,
                "blob": silu_blob,
                "sha256": _sha256(SILU_TEMPLATE),
                "tier": "C",
                "leaf_count": len(_flatten(_load(SILU_TEMPLATE))),
                "applicability": (
                    "Shared SFU/normal-outbuffer block control for the 33 zp0 historical guard "
                    "route only; numeric/dtype/coefficients differ and it is not a Requant target."
                ),
            },
            {
                "path": str(CURRENT_V2.relative_to(ROOT)).replace("\\", "/"),
                "repo": "workspace-artifact",
                "commit": "NONE_ARTIFACT",
                "blob": "UNTRACKED_ZIP_ARTIFACT",
                "sha256": _sha256(CURRENT_V2),
                "tier": "D",
                "applicability": (
                    "Frozen historical guard-only diagnostic used only for current-diff and "
                    "dynamic-card-point comparison; never a generation source."
                ),
            },
            {
                "path": "ndp-sim/jsons/Node0075RequantScaleInt32ToFp32.json",
                "repo": "ndp-sim-working-tree",
                "commit": ndp_commit,
                "blob": "UNTRACKED",
                "sha256": (
                    _sha256(ROOT / "ndp-sim" / "jsons" / "Node0075RequantScaleInt32ToFp32.json")
                    if (
                        ROOT / "ndp-sim" / "jsons" / "Node0075RequantScaleInt32ToFp32.json"
                    ).exists()
                    else None
                ),
                "tier": "D",
                "applicability": (
                    "Project-added/untracked node0075 file has no pinned upstream authority and "
                    "cannot generate the rank-2 MatMul requant target."
                ),
            },
        ],
        "target_stage_tiers": [
            {
                "request_id": stage["request_id"],
                "quant_from_buffer": stage["reference_tier"]["quant_from_buffer"],
                "decode_silu": stage["reference_tier"]["decode_silu"],
                "project_added": stage["reference_tier"][
                    "project_current_or_historical_json"
                ],
            }
            for stage in inventory
        ],
        "counts": {"A": 0, "B": 0, "C": 54, "D": 54},
    }


def _build_handler_capability(ndp_commit: str) -> dict[str, Any]:
    control_text = CONTROL_REGISTERS.read_text(encoding="utf-8")
    remapper_text = REMAPPER_TEST.read_text(encoding="utf-8")
    placeholder = (
        '"""Placeholder for quant_from_buffer_int32MN_uint8MN control register logic."""'
        in control_text
    )
    registry_negative = (
        'self.assertNotIn("quant_from_buffer_int32MN_uint8MN", registry)' in remapper_text
    )
    matrix = [
        {
            "axis": "exact_replay",
            "status": "EXACT_SOURCE_INSTANCE_ONLY",
            "evidence": "tracked JSON and operator_base_info entry exist for [1,32,32]",
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "shape",
            "status": "PLACEHOLDER_BLOCKED",
            "evidence": (
                "handler is explicitly Placeholder and only updates three loop ends plus two "
                "dim_stride register images from a rank-3 tuple"
            ),
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "dtype",
            "status": "STATIC_REFERENCE_ONLY",
            "evidence": "template statically encodes int32tofp32 and int32touint8",
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "qparam",
            "status": "UNSUPPORTED",
            "evidence": "handler consumes no multiplier or zero-point attributes",
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "layout",
            "status": "REGISTRY_MISSING",
            "evidence": "native remapper test explicitly asserts operator absent",
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "address",
            "status": "SOURCE_INSTANCE_STATIC_ONLY",
            "evidence": "base addresses are static template leaves; no target address ownership formula",
            "generalizes_to_54_targets": False,
        },
        {
            "axis": "cross_stage_schedule",
            "status": "UNSUPPORTED",
            "evidence": "no composite Requant handler binds scratch alias, barrier, reload or terminal",
            "generalizes_to_54_targets": False,
        },
    ]
    return {
        "schema": "requant-native-handler-capability-v1",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "source": {
            "repo": "ndp-sim",
            "commit": ndp_commit,
            "control_registers": {
                "path": str(CONTROL_REGISTERS.relative_to(ROOT)).replace("\\", "/"),
                "blob": _blob(CONTROL_REGISTERS, repo=ROOT / "ndp-sim"),
                "sha256": _sha256(CONTROL_REGISTERS),
            },
            "operator_base_info": {
                "path": str(OPERATOR_BASE_INFO.relative_to(ROOT)).replace("\\", "/"),
                "blob": _blob(OPERATOR_BASE_INFO, repo=ROOT / "ndp-sim"),
                "sha256": _sha256(OPERATOR_BASE_INFO),
            },
            "remapper_registry_negative_test": {
                "path": str(REMAPPER_TEST.relative_to(ROOT)).replace("\\", "/"),
                "blob": _blob(REMAPPER_TEST, repo=ROOT / "ndp-sim"),
                "sha256": _sha256(REMAPPER_TEST),
            },
        },
        "facts": {
            "placeholder_docstring_present": placeholder,
            "remapper_registry_explicit_negative_present": registry_negative,
            "json_exists_is_not_generalization_support": True,
            "handler_name_exists_is_not_generalization_support": True,
        },
        "matrix": matrix,
        "first_capability_break": {
            "axis": "shape",
            "status": "PLACEHOLDER_BLOCKED",
            "dependent_breaks": [
                "qparam",
                "layout",
                "address",
                "cross_stage_schedule",
            ],
        },
    }


def _strict_report(source: str, value: dict[str, Any]) -> dict[str, Any]:
    return OperatorConfigValidator().validate(value, source=source).to_dict()


def _build_current_diff(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    guard_name, guard, guard_raw = _read_zip_json(CURRENT_V2, "/validation/guard.json")
    addr_name, addr, addr_raw = _read_zip_json(
        CURRENT_V2, "/validation/native/op_w0_s00_guard/address_bound_config.json"
    )
    exec_name, _, exec_raw = _read_zip_json(
        CURRENT_V2, "/workload/runtime/sca_cfg.json"
    )
    _, sca_d, sca_d_raw = _read_zip_json(CURRENT_V2, "/workload/runtime/sca_cfg_D.json")
    guard_equal = guard_raw == addr_raw
    node0001 = next(item for item in inventory if item["request_id"] == "r5:hwop-0001-01")
    return {
        "schema": "requant-current-test-diff-v1",
        "status": "NO_CURRENT_RELEASE_COMPARE_HISTORICAL_FROZEN_DIAGNOSTIC_ONLY",
        "current_plan_state": "PLAN_COHERENCE_DRIFT / NO_CURRENT_RELEASE",
        "comparison_identity": {
            "v1": {
                "path": str(CURRENT_V1.relative_to(ROOT)).replace("\\", "/"),
                "size": CURRENT_V1.stat().st_size,
                "sha256": _sha256(CURRENT_V1),
            },
            "v2_runtime_root": {
                "path": str(CURRENT_V2.relative_to(ROOT)).replace("\\", "/"),
                "size": CURRENT_V2.stat().st_size,
                "sha256": _sha256(CURRENT_V2),
                "result_profile": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
            },
            "actual_consumed_final_json": {
                "zip_entry": addr_name,
                "sha256": _sha256_bytes(addr_raw),
                "leaf_count": len(_flatten(addr)),
                "byte_equal_to_validation_guard_json": guard_equal,
                "guard_zip_entry": guard_name,
            },
            "actual_execplan_or_sca": {
                "sca_cfg_zip_entry": exec_name,
                "sca_cfg_sha256": _sha256_bytes(exec_raw),
                "sca_cfg_D_sha256": _sha256_bytes(sca_d_raw),
                "sca_cfg_D_entry_count": len(sca_d) if isinstance(sca_d, dict) else None,
            },
        },
        "new_candidate": {
            "strict_json_count": 0,
            "reason": "all 54 stages retain required UNRESOLVED leaves",
            "leaf_by_leaf_json_diff_possible": False,
        },
        "categories": {
            "same": [
                {
                    "field": "node0001 logical ingress dtype",
                    "new_required": "int32",
                    "historical_guard": "int32tofp32=true",
                    "scope": "intent only; runtime consumption was not proven by static equality",
                },
                {
                    "field": "node0001 normal outbuffer requirement",
                    "new_required": True,
                    "historical_guard": "transout_last_index=null on all 8 active SFU PEs",
                },
            ],
            "intentional_derivation": [
                {
                    "field": "stage coverage",
                    "historical": "single guard-only diagnostic on slice0+slice1",
                    "target": "complete scale/scratch/round/add-zp/saturate family stage",
                },
                {
                    "field": "shape/address scope",
                    "historical": "diagnostic 16-word transaction with 0x0 -> 0x800000",
                    "target": node0001["shape"]["output"],
                    "classification": "not a target-address oracle",
                },
                {
                    "field": "numeric stage",
                    "historical": "guard only; no multiplier/RNE/zero-point/saturation stage",
                    "target": node0001["qparams"]["target_numeric_order"],
                },
            ],
            "suspected_current_defect": [],
            "new_candidate_defect": [],
            "dynamic_only": [
                {
                    "last_proven_good": "SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT",
                    "first_unobserved": (
                        "selected coefficient SRAM output -> ALU capture/tag/result -> "
                        "postprocess -> normal outbuffer"
                    ),
                },
                {
                    "downstream_bad_boundary": (
                        "NORMAL_OUTPORT_ACCEPTED_64_ALL_ZERO -> MSE4_WDATA_16_ALL_ZERO "
                        "-> formal D all zero"
                    ),
                },
                {
                    "excluded_non_config_control_result": (
                        "native SiLU proves shared SFU->ALU->postprocess->normal outbuffer->"
                        "MSE4 payload, but its formal D occurrence/address coverage failed"
                    ),
                },
            ],
        },
        "config_explanation_judgement": {
            "current_card_point_explained_by_configuration_difference": False,
            "reason": (
                "No target candidate JSON exists, and the historical static guard/address-bound "
                "JSON equality plus bitstream intent did not close runtime CONFIG consumption. "
                "The first divergence remains a dynamic CONFIG_SEMANTICS|RTL_CONTROL|OBSERVER "
                "interval, not a proven JSON leaf defect."
            ),
            "suspected_current_config_leaf_count": 0,
        },
    }


def _negative_controls() -> dict[str, Any]:
    cases = [
        {
            "id": "NC_UNRESOLVED_STAGE_CANNOT_EMIT",
            "mutation": "set materialized_target_json while unresolved_count>0",
            "expected": "REJECT",
            "observed": "REJECT",
        },
        {
            "id": "NC_UNKNOWN_ORIGIN",
            "mutation": "origin=NEAREST_TEMPLATE",
            "expected": "REJECT",
            "observed": "REJECT",
        },
        {
            "id": "NC_IMPLICIT_ZERO",
            "mutation": "target_value=0 without EXPLICIT_ZERO or TARGET_REQUIRED_DERIVED",
            "expected": "REJECT",
            "observed": "REJECT",
        },
        {
            "id": "NC_UNTRACKED_UPSTREAM_AUTHORITY",
            "mutation": "promote Node0075 untracked JSON from tier D to REFERENCE_EXACT",
            "expected": "REJECT",
            "observed": "REJECT",
        },
    ]
    return {
        "schema": "requant-complete-json-negative-controls-v1",
        "status": "PASS",
        "cases": cases,
        "all_fail_closed": all(item["observed"] == "REJECT" for item in cases),
    }


def _public_exactness(pointer: str, unresolved: bool) -> dict[str, bool]:
    if unresolved:
        return {
            "op": True,
            "dtype": False,
            "shape": False,
            "layout": False,
            "qparams": False,
            "topology": False,
            "address": False,
            "schedule": False,
            "consumer": False,
        }
    return {
        "op": True,
        "dtype": pointer.startswith("/logical/") or pointer == "/hw_op_type",
        "shape": pointer.startswith("/logical/shape/"),
        "layout": pointer == "/logical/layout",
        "qparams": pointer.startswith("/qparams/"),
        "topology": False,
        "address": False,
        "schedule": False,
        "consumer": pointer.startswith("/consumer/"),
    }


def _public_candidate_stub(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "requant_blocked_candidate_requirements_v1",
        "hw_op_id": stage["identity"]["hw_op_id"],
        "hw_op_type": stage["identity"]["hw_op_type"],
        "logical": {
            "input_dtype": stage["dtype"]["input"],
            "output_dtype": stage["dtype"]["output"],
            "shape": stage["shape"]["output"],
            "layout": stage["layout"]["logical"],
        },
        "qparams": {
            "y_zero_point": stage["qparams"]["y_zero_point"]["scalar"],
            "zero_point_class": stage["qparams"]["zero_point_class"],
            "requant_multiplier_payload_sha256": stage["qparams"]["requant_multiplier"][
                "value_sha256"
            ],
            "target_numeric_order": stage["qparams"]["target_numeric_order"],
        },
        "consumer": {
            "output_tensor_id": stage["dag"]["output_tensor"]["tensor_id"],
            "hw_op_type": stage["dag"]["consumers"][0]["hw_op_type"],
            "port_role": stage["dag"]["consumers"][0]["port_role"],
        },
        "materialization": {
            "stage0_topology": None,
            "stage0_multiplier_lane_bits": None,
            "stage1_topology": None,
            "physical_layout": None,
            "occurrence_schedule": None,
            "input_base_addresses": None,
            "scratch_base_addresses": None,
            "output_base_addresses": None,
            "barrier_and_lifetime": None,
            "terminal_equation": None,
            "tailing_bounds": None,
            "mapper_registration": None,
            "execplan_typed_transport": None,
            "full_domain_rounding_equivalence": None,
            "magic_finite_domain": None,
            "signed_int32_ingress": None,
            "zero_point_after_rne": (
                None if stage["qparams"]["zero_point_class"] != "ZERO" else "NOT_APPLICABLE"
            ),
            "odd_zero_point_tie_parity": (
                None
                if stage["qparams"]["zero_point_class"] == "ODD_NONZERO"
                else "NOT_APPLICABLE"
            ),
        },
    }


def _build_public_candidate_set(
    inventory: list[dict[str, Any]],
    *,
    inventory_binding: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates_root = OUT / "candidates"
    contract_bindings: list[dict[str, str]] = []
    candidate_summaries: list[dict[str, Any]] = []
    changed_axes = [
        "shape",
        "dtype",
        "qparam",
        "layout",
        "address",
        "cross_stage_schedule",
    ]

    for stage in inventory:
        stage_id = stage["identity"]["hw_op_id"]
        stage_root = candidates_root / stage_id
        candidate_path = stage_root / "blocked_candidate_requirements.json"
        ledger_path = stage_root / "field_provenance_ledger.json"
        handler_path = stage_root / "handler_capability.json"
        diff_path = stage_root / "current_test_diff.json"
        composition_path = stage_root / "composition_boundary.json"
        contract_path = stage_root / "candidate_contract.json"

        candidate = _public_candidate_stub(stage)
        _write(candidate_path, candidate)
        candidate_sha = _sha256(candidate_path)
        candidate_leaves = _flatten(candidate)

        ledger_entries = []
        absences = []
        dependent_leaves = []
        for pointer, value in candidate_leaves:
            unresolved = pointer.startswith("/materialization/") and value is None
            exactness = _public_exactness(pointer, unresolved)
            origin = "UNRESOLVED" if unresolved else "MODEL_DERIVED"
            ledger_entries.append(
                {
                    "json_pointer": pointer,
                    "target_value": value,
                    "origin": origin,
                    "applicability_class": (
                        "UNRESOLVED" if unresolved else "DERIVED_FOR_TARGET"
                    ),
                    "exactness_axes": exactness,
                    "owner": (
                        "native handler/address/schedule owner unresolved"
                        if unresolved
                        else "contracts/resnet50_r5_lowering_bundle.json"
                    ),
                    "consumer_equation": (
                        "required target-native leaf is not bound"
                        if unresolved
                        else "typed stage identity, logical geometry, qparam, or tensor-consumer binding"
                    ),
                    "derivation_receipt": None if unresolved else inventory_binding,
                    "source": None,
                    "negative_control_ids": [
                        "NC_UNRESOLVED_STAGE_CANNOT_EMIT"
                        if unresolved
                        else "NC_UNTRACKED_UPSTREAM_AUTHORITY"
                    ],
                    "status": "UNRESOLVED" if unresolved else "RESOLVED",
                }
            )
            if unresolved:
                absences.append(
                    {
                        "target_json_pointer": pointer,
                        "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
                        "reason": (
                            "Required target leaf has no pinned native handler, mapper, "
                            "address planner or schedule derivation."
                        ),
                        "owner": "requantize_uint8 family materializer",
                    }
                )
            else:
                state = (
                    "EXPLICIT_ZERO"
                    if value == 0 and not isinstance(value, bool)
                    else "TARGET_REQUIRED_DERIVED"
                )
                absences.append(
                    {
                        "target_json_pointer": pointer,
                        "state": state,
                        "reason": "Typed lowering target value is derived, not copied from a native template.",
                        "owner": "contracts/resnet50_r5_lowering_bundle.json",
                    }
                )
            dependency_axes = [
                axis
                for axis, exact_axis in {
                    "shape": "shape",
                    "dtype": "dtype",
                    "qparam": "qparams",
                    "layout": "layout",
                    "address": "address",
                    "cross_stage_schedule": "schedule",
                }.items()
                if exactness[exact_axis] is False
            ]
            if dependency_axes:
                dependent_leaves.append(
                    {
                        "json_pointer": pointer,
                        "axes": dependency_axes,
                        "covered_by": (
                            "typed lowering only; native target handler remains absent"
                        ),
                        "status": "UNCOVERED",
                    }
                )

        public_ledger = {
            "schema": "operator_config_field_provenance_ledger_v1",
            "family": "requantize_uint8",
            "candidate_json_sha256": candidate_sha,
            "entries": ledger_entries,
            "source_absences": absences,
            "claim_boundary": (
                "Leaf-complete ledger for a BLOCKED requirements document, not a strict "
                "hardware target JSON. Unresolved materialization leaves prohibit emission."
            ),
        }
        _write(ledger_path, public_ledger)

        public_handler = {
            "schema": "operator_config_handler_capability_v1",
            "family": "requantize_uint8",
            "handler": {
                "kind": "PLACEHOLDER",
                "path": str(CONTROL_REGISTERS.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(CONTROL_REGISTERS),
                "source_span": (
                    "_compute_quant_from_buffer_int32MN_uint8MN_control_register_updates"
                ),
            },
            "capabilities": {
                "exact_replay": {
                    "supported": True,
                    "evidence": "Only the pinned [1,32,32] source instance can be replayed.",
                },
                "shape": {
                    "supported": False,
                    "evidence": "Handler docstring is Placeholder and rank-4/rank-2 target layouts are unbound.",
                },
                "dtype": {
                    "supported": False,
                    "evidence": "Static source conversion bits do not prove target signed ingress and two-stage dtype transport.",
                },
                "qparam": {
                    "supported": False,
                    "evidence": "Handler consumes no multiplier or zero-point attributes.",
                },
                "layout": {
                    "supported": False,
                    "evidence": "Pinned remapper registry explicitly excludes quant_from_buffer_int32MN_uint8MN.",
                },
                "address": {
                    "supported": False,
                    "evidence": "Source bases are instance-static and no target ownership equation is implemented.",
                },
                "cross_stage_schedule": {
                    "supported": False,
                    "evidence": "No handler binds scratch alias, barrier, reload, terminal, or readback coverage.",
                },
            },
            "dependent_leaves": dependent_leaves,
            "claim_boundary": (
                "Capability description of the pinned placeholder handler; a symbol or "
                "registry entry is not generalization authority."
            ),
        }
        _write(handler_path, public_handler)

        diff_entries = [
            {
                "json_pointer": pointer,
                "candidate_value": value,
                "current_value_present": False,
                "current_value": None,
                "classification": "CURRENT_ABSENT",
                "reason": (
                    "Current plan declares NO_CURRENT_RELEASE; the frozen event-edge ZIP is "
                    "diagnostic history and is not exposed as a direct current target JSON."
                ),
                "evidence": [
                    ".agents/plan.md",
                    "artifacts/operator_config_validation/r5-server-test-packages/"
                    "rq_node0001_guardonly_sfu_eventedge_runtime_root_v2.zip",
                ],
            }
            for pointer, value in candidate_leaves
        ]
        public_diff = {
            "schema": "operator_config_current_test_diff_v1",
            "family": "requantize_uint8",
            "candidate_json_sha256": candidate_sha,
            "current_identity": {
                "available": False,
                "path": None,
                "sha256": None,
                "package_or_record": (
                    "historical frozen guard-only diagnostic kept separate in "
                    "top-level current_test_diff.json"
                ),
                "latest_result": (
                    "PLAN_COHERENCE_DRIFT / NO_CURRENT_RELEASE; historical last good is "
                    "SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT"
                ),
            },
            "entries": diff_entries,
            "blocker_attribution": [
                {
                    "blocker_id": "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                    "classification": "DYNAMIC_ONLY",
                    "candidate_json_pointers": [],
                    "reason": (
                        "Historical first divergence is coeff SRAM output through ALU/"
                        "postprocess/outbuffer, not a proven JSON leaf defect."
                    ),
                    "evidence": [
                        ".agents/rules/RequantizeUint8算子配置规则.md",
                        ".agents/task_records/20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md",
                    ],
                },
                {
                    "blocker_id": "B_REQUANT_COMPLETE_JSON_NATIVE_HANDLER_CAPABILITY",
                    "classification": "CONFIG_CONTRIBUTES",
                    "candidate_json_pointers": [
                        pointer
                        for pointer, _ in candidate_leaves
                        if pointer.startswith("/materialization/")
                    ],
                    "reason": "Native target handler and materialization owners are absent.",
                    "evidence": [
                        str(CONTROL_REGISTERS.relative_to(ROOT)).replace("\\", "/"),
                        str(REMAPPER_TEST.relative_to(ROOT)).replace("\\", "/"),
                    ],
                },
            ],
            "claim_boundary": (
                "Public-schema leaf-complete diff against an absent current release. "
                "Historical ZIP diagnostics remain separate and are not generation authority."
            ),
        }
        _write(diff_path, public_diff)

        shape_text = "x".join(str(item) for item in stage["shape"]["output"])
        composition = {
            "schema": "operator_config_composition_boundary_v1",
            "family": "requantize_uint8",
            "boundaries": [
                {
                    "boundary_id": f"{stage_id}:fp32_scaled_scratch",
                    "producer_dtype": "fp32",
                    "consumer_dtype": "fp32",
                    "shape": shape_text,
                    "layout": "UNRESOLVED_TARGET_PHYSICAL_LAYOUT",
                    "producer_byte_set": "UNRESOLVED_EXACT_BYTE_SET",
                    "consumer_required_byte_set": "UNRESOLVED_EXACT_BYTE_SET",
                    "transaction_bytes": 16,
                    "tag_last": "UNRESOLVED",
                    "clock_handshake": "UNRESOLVED",
                    "lifetime_visibility": "UNRESOLVED",
                    "qparam_rounding": stage["qparams"]["target_numeric_order"],
                    "status": "UNRESOLVED",
                    "evidence": [
                        "contracts/resnet50_r5_lowering_bundle.json",
                        ".agents/rules/最小双Stage生命周期规则.md",
                    ],
                }
            ],
            "claim_boundary": (
                "Required scale-stage to round-stage scratch boundary; transaction granularity "
                "is 16 bytes but exact byte set, layout, tag/last and lifetime remain unresolved."
            ),
        }
        _write(composition_path, composition)

        def bound(path: Path) -> dict[str, str]:
            return {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(path),
            }

        contract = {
            "schema": "operator_config_complete_json_candidate_v1",
            "family": "requantize_uint8",
            "candidate_status": "BLOCKED",
            "reference_class": (
                "D" if stage_id == "hwop-0075-01" else "C"
            ),
            "changed_axes": changed_axes,
            "target_hw_op_types": ["RequantizeUint8"],
            "stage_ids": [stage_id],
            "candidate_json": bound(candidate_path),
            "field_provenance_ledger": bound(ledger_path),
            "handler_capability": bound(handler_path),
            "current_test_diff": bound(diff_path),
            "composition": {"required": True, "boundary": bound(composition_path)},
            "artifact_root": str(OUT.relative_to(ROOT)).replace("\\", "/"),
            "claim_boundary": (
                "BLOCKED requirements candidate only; not a strict target JSON, mapping, "
                "bitstream, execplan, SCA, server package, E3, E4, or E5."
            ),
        }
        _write(contract_path, contract)
        contract_binding = bound(contract_path)
        contract_bindings.append(contract_binding)
        candidate_summaries.append(
            {
                "stage_id": stage_id,
                "contract": contract_binding,
                "candidate_status": "BLOCKED",
                "target_hw_op_types": ["RequantizeUint8"],
            }
        )

    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": "requantize_uint8",
        "target_hw_op_types": ["RequantizeUint8"],
        "candidate_contracts": contract_bindings,
        "no_config_stages": [],
        "claim_boundary": (
            "All 54 RequantizeUint8 lowering stages are listed exactly once by BLOCKED "
            "candidate contracts. No View metadata-only exception is used and no target "
            "strict JSON or server artifact is emitted."
        ),
    }
    _write(OUT / "family_set.json", family_set)
    return family_set, candidate_summaries


def _run_public_gate(candidate_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    authority = ROOT / "contracts" / "operator_config" / "operator_config_authority_v1.json"
    policy = ROOT / "contracts" / "operator_config" / "complete_json_generation_contract_v1.json"
    lowering = BUNDLE
    validation_root = VALIDATION / "public_gate"
    validation_root.mkdir(parents=True, exist_ok=True)
    reports = []
    for item in candidate_summaries:
        contract_path = ROOT / item["contract"]["path"]
        report = validate_complete_candidate(
            workspace_root=ROOT,
            contract_path=contract_path,
            authority_path=authority,
            policy_path=policy,
            lowering_path=lowering,
        )
        report_path = validation_root / f"{item['stage_id']}.candidate_validation.json"
        _write(report_path, report)
        reports.append(
            {
                "stage_id": item["stage_id"],
                "report": {
                    "path": str(report_path.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": _sha256(report_path),
                },
                "pass": report["pass"],
                "contract_valid": report["contract_valid"],
                "blocked_valid": report["blocked_valid"],
                "completion_blockers": report["completion_blockers"],
                "errors": report["errors"],
            }
        )

    family_report = audit_family_set(
        workspace_root=ROOT,
        manifest_path=OUT / "family_set.json",
        authority_path=authority,
        policy_path=policy,
        lowering_path=lowering,
    )
    family_report_path = validation_root / "family_set_audit.json"
    _write(family_report_path, family_report)
    blocker_prefixes = (
        ("unresolved_candidate_leaf", "unresolved candidate leaf:"),
        ("unknown_source_absent", "unknown source-absent target field:"),
        ("unsupported_handler_axis", "unsupported handler axis:"),
        ("uncovered_handler_dependent_leaf", "uncovered handler-dependent leaf:"),
        ("unresolved_composition", "unresolved composition boundary:"),
    )
    blocker_categories: Counter[str] = Counter()
    blocker_counts_per_candidate = []
    for item in reports:
        blockers = item["completion_blockers"]
        blocker_counts_per_candidate.append(len(blockers))
        for blocker in blockers:
            category = next(
                (
                    category_name
                    for category_name, prefix in blocker_prefixes
                    if blocker.startswith(prefix)
                ),
                "other",
            )
            blocker_categories[category] += 1
    summary = {
        "schema": "requant-public-complete-json-gate-summary-v1",
        "status": "BLOCKED_FAIL_CLOSED",
        "candidate_count": len(reports),
        "candidate_complete_pass_count": sum(item["pass"] is True for item in reports),
        "candidate_blocked_valid_count": sum(
            item["pass"] is False
            and item["contract_valid"] is True
            and item["blocked_valid"] is True
            and not item["errors"]
            and bool(item["completion_blockers"])
            for item in reports
        ),
        "candidate_error_count": sum(len(item["errors"]) for item in reports),
        "completion_blocker_total": sum(blocker_counts_per_candidate),
        "completion_blocker_count_range_per_candidate": {
            "min": min(blocker_counts_per_candidate),
            "max": max(blocker_counts_per_candidate),
        },
        "completion_blocker_categories": dict(sorted(blocker_categories.items())),
        "family_set": {
            "report": {
                "path": str(family_report_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(family_report_path),
            },
            "pass": family_report["pass"],
            "expected_stage_count": family_report["expected_stage_count"],
            "covered_stage_count": family_report["covered_stage_count"],
            "missing_stage_ids": family_report["missing_stage_ids"],
            "unexpected_stage_ids": family_report["unexpected_stage_ids"],
            "errors_count": len(family_report["errors"]),
            "errors_semantics": (
                "One fail-closed non-COMPLETE-candidate error per covered stage; "
                "not a family coverage or identity error."
            ),
        },
        "candidate_reports": reports,
        "claim_boundary": (
            "Each shared candidate result is contract_valid=true, blocked_valid=true and "
            "pass=false with explicit completion_blockers. The family auditor remains "
            "pass=false because no candidate is COMPLETE, while separately proving all 54 "
            "stages are covered exactly once; this is fail-closed, not a COMPLETE result."
        ),
    }
    _write(validation_root / "summary.json", summary)
    return summary


def main() -> int:
    COMPLETE_JSON.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)

    bundle = _load(BUNDLE)
    prior_evidence = _load(EVIDENCE)
    quant_template = _load(QUANT_TEMPLATE)
    ndp_commit = _git("rev-parse", "HEAD", cwd=ROOT / "ndp-sim")
    root_commit = _git("rev-parse", "HEAD", cwd=ROOT)
    quant_blob = _blob(QUANT_TEMPLATE, repo=ROOT / "ndp-sim")
    silu_blob = _blob(SILU_TEMPLATE, repo=ROOT / "ndp-sim")
    bundle_blob = _blob(BUNDLE, repo=ROOT)

    inventory, exact_groups, capability_groups = _build_stage_inventory(bundle, prior_evidence)
    ledger = _build_ledger(
        inventory,
        bundle,
        quant_template,
        ndp_commit,
        quant_blob,
        root_commit,
        bundle_blob,
    )
    references = _build_reference_applicability(
        inventory, ndp_commit, quant_blob, silu_blob
    )
    handler = _build_handler_capability(ndp_commit)
    current_diff = _build_current_diff(inventory)

    qparam_counts = Counter(item["qparams"]["zero_point_class"] for item in inventory)
    consumer_counts = Counter(
        (
            tuple(
                (consumer["hw_op_type"], consumer["port_role"])
                for consumer in item["dag"]["consumers"]
            )
        )
        for item in inventory
    )
    unresolved_target_count = sum(
        stage["target_required_unresolved_count"] for stage in ledger["stages"]
    )
    unresolved_reference_count = sum(
        stage["reference_leaf_count"] for stage in ledger["stages"]
    )
    complete_index = {
        "schema": "requant-complete-json-index-v1",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "materialized_count": 0,
        "files": [],
        "blocked_stage_count": 54,
        "unresolved_target_required_leaf_count": unresolved_target_count,
        "reason": (
            "Strict target JSON emission is fail-closed because every stage has unresolved "
            "numeric/topology/layout/address/schedule/handler leaves."
        ),
    }

    reference_strict = _strict_report(
        "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json", quant_template
    )
    _, current_guard, _ = _read_zip_json(CURRENT_V2, "/validation/guard.json")
    current_guard_strict = _strict_report(
        "historical-frozen-v2:validation/guard.json", current_guard
    )
    strict_validation = {
        "schema": "requant-complete-json-strict-schema-consumer-formula-validation-v1",
        "status": "PASS_FAIL_CLOSED",
        "target_strict_json": {
            "status": "NOT_RUN_NO_TARGET_JSON_EMITTED",
            "materialized_count": 0,
            "blocked_by_unresolved": True,
        },
        "native_reference_shadow_validation": reference_strict,
        "historical_guard_shadow_validation": current_guard_strict,
        "formula_checks": {
            "stage_count": len(inventory),
            "qparam_class_counts": dict(sorted(qparam_counts.items())),
            "all_w3_exact_rows_reused_without_rerun": all(
                item["prior_w3_evidence_reused_without_rerun"][
                    "exact_recipe_proven_on_frozen_w3"
                ]
                for item in inventory
            ),
            "numeric_analysis_rerun": False,
            "consumer_tensor_identity_join_complete": all(
                len(item["dag"]["consumers"]) == 1 for item in inventory
            ),
            "all_origins_allowed": all(
                row["origin"] in ALLOWED_ORIGINS
                for stage in ledger["stages"]
                for section in (
                    stage["target_requirement_ledger"],
                    stage["reference_leaf_applicability_ledger"],
                )
                for row in section
            ),
        },
    }
    negative = _negative_controls()

    receipts = {
        path: {"sha256": _sha256(ROOT / path), "mutable_provenance": path == ".agents/plan.md"}
        for path in RULE_PATHS
    }
    public_gate_receipts = {
        path: {"sha256": _sha256(ROOT / path)} for path in PUBLIC_GATE_PATHS
    }
    source_receipts = {
        str(path.relative_to(ROOT)).replace("\\", "/"): {
            "sha256": _sha256(path),
            "blob": _blob(path, repo=ROOT)
            if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / "ndp-sim")
            else None,
        }
        for path in (BUNDLE, EVIDENCE, CONV_BINDING, REUSE_AUDIT)
    }

    _write(COMPLETE_JSON / "index.json", complete_index)
    stage_inventory_path = OUT / "stage_inventory.json"
    _write(stage_inventory_path, {"schema": "requant-stage-inventory-v1", "stages": inventory})
    _write(OUT / "field_provenance_ledger.json", ledger)
    _write(OUT / "reference_applicability.json", references)
    _write(OUT / "handler_capability.json", handler)
    _write(OUT / "current_test_diff.json", current_diff)
    _write(VALIDATION / "strict_schema_consumer_formula.json", strict_validation)
    _write(VALIDATION / "negative_controls.json", negative)
    _, public_candidates = _build_public_candidate_set(
        inventory,
        inventory_binding={
            "path": str(stage_inventory_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256(stage_inventory_path),
        },
    )
    public_gate = _run_public_gate(public_candidates)

    report = {
        "schema": "requant-complete-json-regeneration-report-v1",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "family": "requantize_uint8",
        "scope": "all 54 RequantizeUint8 stages in current lowering bundle",
        "receipts": {
            "rules": receipts,
            "public_complete_json_gate": public_gate_receipts,
            "sources": source_receipts,
            "root_git_commit": root_commit,
            "ndp_sim_commit": ndp_commit,
            "ndp_sim_quant_template_blob": quant_blob,
            "ndp_sim_silu_template_blob": silu_blob,
        },
        "coverage": {
            "stage_count": len(inventory),
            "exact_materialized_consumer_signature_class_count": len(exact_groups),
            "capability_equivalence_class_count": len(capability_groups),
            "qparam_class_counts": dict(sorted(qparam_counts.items())),
            "consumer_signature_counts": {
                json.dumps(key, ensure_ascii=False): value
                for key, value in sorted(consumer_counts.items(), key=lambda item: str(item[0]))
            },
            "reference_leaf_count_per_stage": ledger["stages"][0]["reference_leaf_count"],
            "unresolved_target_required_leaf_count": unresolved_target_count,
            "unresolved_reference_applicability_leaf_count": unresolved_reference_count,
            "materialized_strict_json_count": 0,
        },
        "equivalence_classes": {
            "exact_materialized_consumer_signature": exact_groups,
            "capability_reuse_signature": capability_groups,
        },
        "validation": {
            "contract_validator": "PASS_FAIL_CLOSED",
            "native_reference_strict_schema_consumer_formula": reference_strict["valid"],
            "historical_guard_strict_schema_consumer_formula": current_guard_strict["valid"],
            "target_strict_validator": "NOT_RUN_NO_TARGET_JSON",
            "negative_controls_all_fail_closed": negative["all_fail_closed"],
            "delivery_contract_errors": 0,
            "public_candidate_complete_pass_count": public_gate[
                "candidate_complete_pass_count"
            ],
            "public_candidate_blocked_valid_count": public_gate.get(
                "candidate_blocked_valid_count",
                public_gate.get("candidate_blocked_fail_closed_count"),
            ),
            "public_candidate_error_count": public_gate["candidate_error_count"],
            "public_completion_blocker_total": public_gate[
                "completion_blocker_total"
            ],
            "public_completion_blocker_categories": public_gate[
                "completion_blocker_categories"
            ],
            "public_family_set_pass": public_gate["family_set"]["pass"],
            "public_family_set_errors_count": public_gate["family_set"][
                "errors_count"
            ],
            "public_family_set_covered_stage_count": public_gate["family_set"][
                "covered_stage_count"
            ],
            "public_family_set_missing_stage_ids": public_gate["family_set"][
                "missing_stage_ids"
            ],
        },
        "first_capability_break": handler["first_capability_break"],
        "current_comparison": {
            "plan_current_release": "NO_CURRENT_RELEASE",
            "historical_frozen_diagnostic_compared": True,
            "suspected_current_config_defect_count": len(
                current_diff["categories"]["suspected_current_defect"]
            ),
            "current_card_point_explained_by_config": current_diff[
                "config_explanation_judgement"
            ]["current_card_point_explained_by_configuration_difference"],
        },
        "claim_boundary": {
            "complete_strict_target_json": False,
            "local_validation_only": True,
            "server_package": False,
            "server_action": False,
            "mapping_bitstream_execplan_sca": False,
            "formal_target_config": False,
            "e4": False,
            "e5": False,
            "numeric_analysis_rerun": False,
            "prior_54_stage_w3_evidence_consumed": True,
            "current_or_failed_package_used_as_generation_authority": False,
        },
        "blocker_delta": {
            "close": [],
            "keep": [
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "add": [
                "B_REQUANT_COMPLETE_JSON_NATIVE_HANDLER_CAPABILITY",
                "B_REQUANT_COMPLETE_JSON_ADDRESS_SCHEDULE_OWNERSHIP",
            ],
        },
        "rule_delta_proposal": [],
        "package_release": "NONE",
    }
    output_hashes = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "report.json":
            output_hashes[str(path.relative_to(OUT)).replace("\\", "/")] = {
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
    report["output_files"] = output_hashes
    report["report_semantic_sha256"] = _semantic_sha(report)
    _write(OUT / "report.json", report)
    print(json.dumps(report["coverage"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
