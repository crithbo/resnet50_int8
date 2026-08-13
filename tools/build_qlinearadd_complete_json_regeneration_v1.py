from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinearadd"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
STAGE0 = (
    ROOT
    / "configs/qlinearadd_stage0_config_only/"
    "qlinearadd_stage0_config_only_v1.json"
)
HARDWARE_APPROVAL = ROOT / "contracts/hardware_approval.json"
CURRENT_CONFIG = (
    ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36"
)
CURRENT_FINAL = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36/execplan/pipeline_output"
)
CURRENT_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_cout32_v36.zip"
)
V35_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v35-return-analysis/report.json"
)
V35_TASK = (
    ROOT
    / ".agents/task_records/"
    "20260806_qlinearadd_node0007_v35_return_analysis.md"
)

ROOT_COMMIT = "75186a2462acbb4d3a12d0466f297c0c779cc9d7"
NDP_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOWERING_BLOB = "56e21d47d47a239a687fdc29987eeae1ea356b3f"
STAGE0_BLOB = "6a575aa7a239db792289e0779dc856b7f61d1e4c"
HARDWARE_APPROVAL_BLOB = "0fa69fd9b20bbdf0be098be7f53ec1af6af03a1b"

NATIVE_REFS = {
    "add_dequant": {
        "path": "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json",
        "blob": "41c502ce87ac7712c42dcc6214ecb76f3bc4c06b",
        "grade": "C",
        "reason": (
            "same GA/stream/buffer block and uint8 inputs, but native affine "
            "reassociation and FP32 terminal are not W3 QLinearAdd semantics"
        ),
    },
    "prefill_fp32_add": {
        "path": "ndp-sim/jsons/prefill_add_fp32MN_fp32MN_fp32MN.json",
        "blob": "e9c454f006d654aec850d2148f37253cab251bfb",
        "grade": "B",
        "reason": "same FP32 add primitive, source shape/layout differs",
    },
    "decode_fp32_add": {
        "path": "ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json",
        "blob": "fa0c87fc9080137732036ce5f23ffb600f522510",
        "grade": "B",
        "reason": "same FP32 add primitive and eight-lane topology, source shape differs",
    },
    "quant_tail": {
        "path": "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
        "blob": "959e759e81eea358f52680c091f2dfa1535f564d",
        "grade": "C",
        "reason": (
            "same GA/buffer/write blocks, but QAdd tail input dtype/order and "
            "two-stage FP32 reciprocal then RNE/magic composition differ"
        ),
    },
}

PHYSICAL_STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)
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


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def escape(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            yield from leaves(value[key], f"{pointer}/{escape(str(key))}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaves(item, f"{pointer}/{index}")
    else:
        yield pointer or "/", value


def consumer_equation(pointer: str) -> str:
    if "/dram_loop_configs/" in pointer:
        return "IGA LC: start/end/stride/last_index -> ordered occurrence/address feedback"
    if "/buffer_loop_configs/" in pointer:
        return "Buffer_AG ROW/COL paired tag equation -> accepted buffer transaction"
    if "/stream_engine/" in pointer:
        return "Stream engine: base + dim_stride/idx_size/buf_spatial -> byte request"
    if "/general_array/PE_array/" in pointer:
        return "GA selected PE opcode/inport source/constants -> qualified lane output"
    if "/general_array/inport/" in pointer:
        return "GA inport conversion/mask -> operand capture byte/lane set"
    if "/general_array/outport/" in pointer:
        return "GA outport selection/conversion -> Buffer accepted-write supply"
    if "/buffer_config/" in pointer:
        return "Buffer bank mask/row/lifetime -> valid bank-byte set and visibility"
    if "/lc_pe_configs/" in pointer:
        return "LC PE route/enable -> selected loop carrier and terminal"
    if "/CONFIG/" in pointer:
        return "Global config manager enable stream -> active register write"
    return "typed lowering/composite schedule consumer"


def source_record(
    *,
    repository: str,
    commit: str,
    blob: str,
    path: str,
    pointer: str,
    value: Any,
    file_sha256: str | None = None,
) -> dict[str, Any]:
    record = {
        "repository": repository,
        "commit": commit,
        "blob": blob,
        "path": path,
        "json_pointer": pointer,
        "value": value,
    }
    if file_sha256 is not None:
        record["file_sha256"] = file_sha256
    return record


def resolved_leaf(
    *,
    target_id: str,
    pointer: str,
    value: Any,
    origin: str,
    source: dict[str, Any],
    derivation: str,
    owner: str,
    equation: str,
    applicability: str = "TARGET_REQUIRED_DERIVED",
    exactness_axes: dict[str, bool] | None = None,
) -> dict[str, Any]:
    if origin not in ALLOWED_ORIGINS:
        raise ValueError(origin)
    return {
        "target_id": target_id,
        "physical_stage": None,
        "json_pointer": pointer,
        "target_value": value,
        "origin": origin,
        "source": source,
        "applicability": applicability,
        "exactness_axes": exactness_axes
        or {
            "typed_signature": True,
            "shape": True,
            "dtype": True,
            "layout": True,
            "qparam": True,
            "address": False,
            "schedule": False,
            "consumer": True,
        },
        "derivation": derivation,
        "owner": owner,
        "current_consumer_equation": equation,
        "status": "RESOLVED",
        "default_state": applicability,
        "negative_control": "value/hash/typed-role mutation must fail equality",
        "claim_boundary": "logical/composite contract leaf only; not a strict hardware config leaf",
    }


def unresolved_hardware_leaf(
    *,
    target_id: str,
    stage: str,
    pointer: str,
    comparison_value: Any,
    comparison_path: Path,
) -> dict[str, Any]:
    default_state = (
        "EXPLICIT_NULL_INACTIVE"
        if comparison_value is None
        else (
            "EXPLICIT_ZERO"
            if comparison_value in (0, "0", "0x00000000")
            else "SOURCE_ABSENT_UNKNOWN_FOR_TARGET"
        )
    )
    return {
        "target_id": target_id,
        "physical_stage": stage,
        "json_pointer": (
            f"/targets/{escape(target_id)}/physical_stages/{stage}/"
            f"strict_hardware_json{pointer}"
        ),
        "target_value": None,
        "origin": "UNRESOLVED",
        "source": source_record(
            repository="resnet50_int8 project working tree",
            commit="NONE_PROJECT_ADDED_COMPARISON_ONLY",
            blob="NONE_NOT_UPSTREAM_AUTHORITY",
            path=comparison_path.relative_to(ROOT).as_posix(),
            pointer=pointer,
            value=comparison_value,
            file_sha256=sha(comparison_path),
        ),
        "applicability": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
        "exactness_axes": {
            "schema": True,
            "typed_signature": target_id == "hwop-0007-00",
            "shape": target_id == "hwop-0007-00",
            "dtype": target_id == "hwop-0007-00",
            "layout": target_id == "hwop-0007-00",
            "qparam": False,
            "address": False,
            "schedule": False,
            "consumer": True,
        },
        "derivation": (
            "No current native QLinearAdd handler proves this target leaf for "
            "the requested shape/qparams/address/schedule. The v36 value is "
            "comparison evidence only and cannot be copied as authority."
        ),
        "owner": "target handler/encoder/RTL/address planner/scheduler unresolved",
        "current_consumer_equation": consumer_equation(pointer),
        "status": "UNRESOLVED",
        "default_state": default_state,
        "comparison_only_value_kind": (
            "EXPLICIT_NULL_INACTIVE"
            if comparison_value is None
            else ("EXPLICIT_ZERO" if comparison_value == 0 else "VALUE")
        ),
        "negative_control": (
            "nearest-template copy, implicit zero/null, or v36 value promotion "
            "to REFERENCE_EXACT must fail closed"
        ),
        "claim_boundary": "required strict hardware leaf; materialization prohibited",
    }


def qparams(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    wanted = {
        "a_scale",
        "a_zero_point",
        "b_scale",
        "b_zero_point",
        "y_scale",
        "y_zero_point",
    }
    result = {}
    for item in request["typed_parameters"]:
        if item["name"] in wanted:
            result[item["name"]] = {
                "value": item["value"]["scalar"],
                "dtype": item["value"]["dtype"],
                "shape": item["value"]["shape"],
                "value_sha256": item["value"]["value_sha256"],
                "float32_bits": item["value"].get("float32_bits"),
            }
    if set(result) != wanted:
        raise ValueError(f"six qparams incomplete: {request['request_id']}")
    return result


def stage_plan(request: dict[str, Any], stage0: dict[str, Any]) -> dict[str, Any]:
    shapes = {
        "a": request["logical_geometry"]["broadcast"]["a_shape"],
        "b": request["logical_geometry"]["broadcast"]["b_shape"],
        "y": request["logical_geometry"]["broadcast"]["output_shape"],
    }
    broadcast = shapes["a"] != shapes["b"]
    allocations = {
        item["name"].split(":")[-1]: item for item in stage0["allocations"]
    }
    plan = {
        "identity": request["identity"],
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "op": "QLinearAddUint8",
        "dtypes": {
            "a": "uint8",
            "b": "uint8",
            "y": "uint8",
            "scratch": "float32",
        },
        "shapes": shapes,
        "layout": {
            "layout_id": "w4_qlinearadd_group4x7_28_candidate_v1",
            "communication_domain": "local",
            "source": "contracts/hardware_approval.json",
        },
        "qparams": qparams(request),
        "padding_tail": {
            "a": "none",
            "b": (
                {
                    "typed_elements": 1000,
                    "physical_elements": 1008,
                    "typed_bytes": 4000,
                    "physical_bytes": 4032,
                    "padding_bytes": 32,
                    "replay_count": 16,
                    "address": "B_SCALED.base + (logical_output_index % 1000) * 4",
                }
                if broadcast
                else "none"
            ),
            "y": "uint8 tail packing required; final exact target JSON unresolved",
        },
        "dag": {
            "physical_stage_order": list(PHYSICAL_STAGES),
            "barriers": stage0["barriers"],
            "W3_order": [
                "a_i32=int32(A)-int32(a_zero_point)",
                "a_f32=float32(a_i32)",
                "a_scaled=round_float32(a_f32*float32(a_scale))",
                "b_i32=int32(B)-int32(b_zero_point)",
                "b_f32=float32(b_i32)",
                "b_scaled=round_float32(b_f32*float32(b_scale))",
                "sum_f32=round_float32(a_scaled+b_scaled)",
                "quotient=round_float32(sum_f32/float32(y_scale))",
                "rounded=RNE_int64(quotient)",
                "shifted=rounded+int64(y_zero_point)",
                "Y=uint8(clamp(shifted,0,255))",
            ],
        },
        "edges": {
            "A": {
                "owner": "upstream producer/execplan input binding",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "lifetime": "through last accepted A dequant read",
            },
            "B": {
                "owner": "upstream producer or immutable initializer/execplan input binding",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "lifetime": "through last accepted B dequant read/replay",
            },
            "A_SCALED": {
                "owner": "QLinearAdd scratch address planner",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "logical_bytes": allocations["A_SCALED"]["logical_size_bytes"],
                "lifetime": allocations["A_SCALED"]["lifetime"],
            },
            "B_SCALED": {
                "owner": "QLinearAdd scratch address planner",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "logical_bytes": allocations["B_SCALED"]["logical_size_bytes"],
                "lifetime": allocations["B_SCALED"]["lifetime"],
            },
            "SUM_F32": {
                "owner": "QLinearAdd scratch address planner",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "logical_bytes": allocations["SUM_F32"]["logical_size_bytes"],
                "lifetime": allocations["SUM_F32"]["lifetime"],
            },
            "Y": {
                "owner": "downstream edge allocator/execplan output binding",
                "address": "UNRESOLVED_TARGET_ADDRESS",
                "lifetime": "from first accepted tail write through downstream last accepted read",
            },
        },
        "physical_stages": {
            stage: {
                "status": "STRICT_HARDWARE_JSON_UNRESOLVED",
                "schema_source": (
                    CURRENT_CONFIG / f"{stage}.json"
                ).relative_to(ROOT).as_posix(),
                "address_owner": (
                    "upstream/edge address planner"
                    if stage in {"op_a_dequant", "op_b_dequant"}
                    else "QLinearAdd scratch/output address planner"
                ),
                "terminal_owner": "stage schedule plus accepted consumer handshake",
            }
            for stage in PHYSICAL_STAGES
        },
        "emission_policy": request["emission_policy"],
        "effective_blockers": [
            "B_ADD_UINT8_REQUANT",
            "B_EXECPLAN_TYPED_TRANSPORT",
        ],
    }
    return plan


def logical_ledger(
    plan: dict[str, Any], request_index: int
) -> list[dict[str, Any]]:
    target_id = plan["identity"]["hw_op_id"]
    records = []
    logical = {
        "identity": plan["identity"],
        "op": plan["op"],
        "dtypes": plan["dtypes"],
        "shapes": plan["shapes"],
        "qparams": plan["qparams"],
        "padding_tail": plan["padding_tail"],
        "layout": plan["layout"],
        "dag": plan["dag"],
        "edges": plan["edges"],
    }
    for pointer, value in leaves(logical):
        full = f"/targets/{escape(target_id)}{pointer}"
        if pointer.startswith("/layout"):
            source = source_record(
                repository="resnet50_int8",
                commit=ROOT_COMMIT,
                blob=HARDWARE_APPROVAL_BLOB,
                path="contracts/hardware_approval.json",
                pointer="/operator_bindings/add",
                value={
                    "layout_id": "w4_qlinearadd_group4x7_28_candidate_v1",
                    "communication_domain": "local",
                },
            )
            origin = "REFERENCE_EXACT"
            derivation = "approved W4 add physical-layout binding"
            owner = "hardware approval"
        elif pointer.startswith("/dag") or pointer.startswith("/edges"):
            source = source_record(
                repository="resnet50_int8",
                commit=ROOT_COMMIT,
                blob=STAGE0_BLOB,
                path=STAGE0.relative_to(ROOT).as_posix(),
                pointer=f"/instances/{request_index}",
                value=value,
                file_sha256=sha(STAGE0),
            )
            origin = (
                "ADDRESS_PLANNER_DERIVED"
                if pointer.endswith("/address") or "/address/" in pointer
                else "SCHEDULE_DERIVED"
            )
            derivation = "stage0 composite DAG/address-owner/lifetime contract"
            owner = "QLinearAdd family schedule/address planner"
        else:
            source = source_record(
                repository="resnet50_int8",
                commit=ROOT_COMMIT,
                blob=LOWERING_BLOB,
                path=LOWERING.relative_to(ROOT).as_posix(),
                pointer=f"/requests/{request_index}",
                value=value,
                file_sha256=sha(LOWERING),
            )
            origin = "MODEL_DERIVED"
            derivation = "typed lowering request and locked W3 initializer identity"
            owner = "typed lowering/model"
        records.append(
            resolved_leaf(
                target_id=target_id,
                pointer=full,
                value=value,
                origin=origin,
                source=source,
                derivation=derivation,
                owner=owner,
                equation=consumer_equation(pointer),
            )
        )
    return records


def main() -> int:
    if OUT.exists():
        raise ValueError(f"fresh analysis path required: {OUT}")
    lowering = load(LOWERING)
    stage0 = load(STAGE0)
    requests = [
        item
        for item in lowering["requests"]
        if item["identity"]["hw_op_type"] == "QLinearAddUint8"
    ]
    instances = {
        item["hw_op_id"]: item for item in stage0["instances"]
    }
    if len(requests) != 17 or len(instances) != 17:
        raise ValueError("QLinearAdd 17-instance inventory differs")
    effective = {
        item["hw_op_id"]: item
        for item in lowering["effective_resolutions"]
        if item["hw_op_id"] in instances
    }
    configs = {
        stage: CURRENT_CONFIG / f"{stage}.json" for stage in PHYSICAL_STAGES
    }
    if not all(path.is_file() for path in configs.values()):
        raise FileNotFoundError("current node0007 six-stage comparison schema incomplete")

    plans = []
    ledger = []
    structural_classes: dict[str, list[str]] = defaultdict(list)
    exact_classes: dict[str, list[str]] = defaultdict(list)
    for request in requests:
        hw_op = request["identity"]["hw_op_id"]
        plan = stage_plan(request, instances[hw_op])
        shape_key = canonical_sha(
            {
                "shapes": plan["shapes"],
                "dtypes": plan["dtypes"],
                "layout": plan["layout"],
                "broadcast": plan["padding_tail"]["b"] != "none",
                "physical_stages": list(PHYSICAL_STAGES),
            }
        )
        exact_key = canonical_sha(
            {
                "structural": shape_key,
                "qparams": plan["qparams"],
                "padding_tail": plan["padding_tail"],
                "dag": plan["dag"]["physical_stage_order"],
            }
        )
        plan["structural_signature_sha256"] = shape_key
        plan["materialized_consumer_signature_sha256"] = exact_key
        structural_classes[shape_key].append(hw_op)
        exact_classes[exact_key].append(hw_op)
        plans.append(plan)
        request_index = lowering["requests"].index(request)
        ledger.extend(logical_ledger(plan, request_index))
        for stage, path in configs.items():
            schema = load(path)
            for pointer, value in leaves(schema):
                ledger.append(
                    unresolved_hardware_leaf(
                        target_id=hw_op,
                        stage=stage,
                        pointer=pointer,
                        comparison_value=value,
                        comparison_path=path,
                    )
                )

    unresolved = [item for item in ledger if item["status"] == "UNRESOLVED"]
    origin_counts = Counter(item["origin"] for item in ledger)
    default_counts = Counter(item["default_state"] for item in ledger)
    inventory = {
        "schema": "qlinearadd-complete-json-target-inventory-v1",
        "family": "qlinearadd",
        "logical_target_stage_count": 17,
        "physical_stage_count": 17 * len(PHYSICAL_STAGES),
        "structural_equivalence_class_count": len(structural_classes),
        "materialized_consumer_signature_class_count": len(exact_classes),
        "structural_equivalence_classes": [
            {
                "signature_sha256": key,
                "members": members,
                "count": len(members),
            }
            for key, members in sorted(structural_classes.items())
        ],
        "materialized_consumer_signature_classes": [
            {
                "signature_sha256": key,
                "members": members,
                "count": len(members),
            }
            for key, members in sorted(exact_classes.items())
        ],
        "targets": plans,
    }

    reference_applicability = {
        "schema": "qlinearadd-native-reference-applicability-v1",
        "pinned_repository": {
            "repository": "uSFrances/ndp-sim",
            "commit": NDP_COMMIT,
        },
        "grades": {
            "A": "exact typed/topology/consumer replay for target",
            "B": "same primitive, shape differs",
            "C": "same hardware block, numeric or dtype/order differs",
            "D": "project-added/untracked/no upstream authority",
        },
        "references": [
            {
                "reference_id": key,
                "repository": "uSFrances/ndp-sim",
                "commit": NDP_COMMIT,
                "path": item["path"],
                "blob": item["blob"],
                "file_sha256": sha(ROOT / item["path"]),
                "grade": item["grade"],
                "reason": item["reason"],
                "target_exact_replay_allowed": False,
            }
            for key, item in NATIVE_REFS.items()
        ]
        + [
            {
                "reference_id": "current_node0007_v36_six_configs",
                "repository": "resnet50_int8 project working tree",
                "commit": "NONE_PROJECT_ADDED_OR_DERIVED",
                "paths": [
                    path.relative_to(ROOT).as_posix() for path in configs.values()
                ],
                "file_sha256": {
                    stage: sha(path) for stage, path in configs.items()
                },
                "grade": "D",
                "reason": (
                    "current test comparison only; project-generated node0007 "
                    "files do not become upstream authority for 16 other targets"
                ),
                "target_exact_replay_allowed": False,
            }
        ],
        "grade_counts": {"A": 0, "B": 2, "C": 2, "D": 1},
    }

    handler_capability = {
        "schema": "qlinearadd-native-handler-capability-matrix-v1",
        "pinned_repository": {
            "repository": "uSFrances/ndp-sim",
            "commit": NDP_COMMIT,
        },
        "worktree_patch_warning": {
            "control_registers_tracked_blob": "6666e16343647e22f7de5ac6213b2d359300c6e7",
            "control_registers_worktree_blob": "d918fa798e239a4fcd0dd01f93b706012d0ce321",
            "json_loader_tracked_blob": "f901c38c4647b1cb441ad4c4fa3005b179b155a8",
            "json_loader_worktree_blob": "78c6324977329d5539f8c9851f97ba70c5b828e3",
            "claim_boundary": "project patches are capabilities to audit, not upstream authority",
        },
        "dimensions": [
            "exact_replay",
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        ],
        "handlers": [
            {
                "op": "QLinearAddUint8",
                "registry_entry": False,
                "handler": None,
                "capabilities": {
                    key: False
                    for key in (
                        "exact_replay",
                        "shape",
                        "dtype",
                        "qparam",
                        "layout",
                        "address",
                        "cross_stage_schedule",
                    )
                },
                "target_support": False,
                "evidence": "no native composite registry/typed six-qparam handler",
            },
            {
                "op": "add_dequant_uint8CWH_uint8CWH_fp32CWH",
                "registry_entry": False,
                "handler": (
                    "model_execplan/src/execution_plan_generator/"
                    "control_registers.py:"
                    "_compute_add_dequant_uint8CWH_uint8CWH_fp32CWH_"
                    "control_register_updates"
                ),
                "handler_classification": "PLACEHOLDER",
                "capabilities": {
                    "exact_replay": True,
                    "shape": False,
                    "dtype": False,
                    "qparam": False,
                    "layout": False,
                    "address": "PARTIAL_NOT_TARGET_COMPLETE",
                    "cross_stage_schedule": False,
                },
                "target_support": False,
                "evidence": (
                    "handler docstring is Placeholder; address-remapping "
                    "test_solver explicitly asserts this op is absent"
                ),
            },
            {
                "op": "prefill_add_fp32MN_fp32MN_fp32MN",
                "registry_entry": True,
                "handler_classification": "PLACEHOLDER",
                "capabilities": {
                    "exact_replay": True,
                    "shape": "LIMITED_SOURCE_MN_ONLY",
                    "dtype": False,
                    "qparam": "NOT_APPLICABLE_TO_FP32_PRIMITIVE",
                    "layout": "LIMITED_SOURCE_LAYOUT_ONLY",
                    "address": "PARTIAL_GENERIC_WRITER",
                    "cross_stage_schedule": False,
                },
                "target_support": False,
                "evidence": "placeholder handler; no ResNet QAdd composite boundary proof",
            },
            {
                "op": "decode_add_fp32N_fp32N_fp32N",
                "registry_entry": "golden-only registry; no ResNet composite entry",
                "handler_classification": "CONSERVATIVE_EXAMPLE",
                "capabilities": {
                    "exact_replay": True,
                    "shape": False,
                    "dtype": False,
                    "qparam": "NOT_APPLICABLE_TO_FP32_PRIMITIVE",
                    "layout": False,
                    "address": "PARTIAL_GENERIC_WRITER",
                    "cross_stage_schedule": False,
                },
                "target_support": False,
                "evidence": "handler updates only LC0.end and says replace once add rules are finalized",
            },
            {
                "op": "quant_from_buffer_int32MN_uint8MN",
                "registry_entry": "source primitive only",
                "handler_classification": "SOURCE_PRIMITIVE_NOT_QADD_TAIL",
                "capabilities": {
                    "exact_replay": True,
                    "shape": False,
                    "dtype": False,
                    "qparam": False,
                    "layout": False,
                    "address": "PARTIAL_GENERIC_WRITER",
                    "cross_stage_schedule": False,
                },
                "target_support": False,
                "evidence": "QAdd tail changes dtype/order/topology and needs six-qparam composition",
            },
        ],
        "composite_result": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "blocking_dimensions": [
            "qparam adaptation/typed six-qparam transport",
            "shape adaptation for all five structural classes",
            "cross-stage schedule and state composition",
            "complete target address binding",
            "exact UINT8 output tail binding",
        ],
    }

    current_v35 = load(V35_REPORT)
    current_diff = {
        "schema": "qlinearadd-complete-json-vs-current-test-diff-v1",
        "candidate_materialized": False,
        "candidate_leaf_diff_performed": False,
        "reason": (
            "No new strict target JSON is legal while required leaves remain "
            "UNRESOLVED; a fabricated candidate-current leaf diff is forbidden."
        ),
        "current_test_identity": {
            "v35_source_sha256": (
                "45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829"
            ),
            "v35_return_report_sha256": sha(V35_REPORT),
            "v35_task_record_sha256": sha(V35_TASK),
            "v36_candidate_package_sha256": sha(CURRENT_PACKAGE),
            "v36_status": "PACKAGE_READY_NOT_RUN_SPLIT_C_ONLY",
            "current_final_fp32_json": (
                CURRENT_FINAL
                / "jsons/op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
            ).relative_to(ROOT).as_posix(),
            "current_execplan": (
                CURRENT_FINAL / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
        },
        "categories": {
            "same": [
                "node0007 logical A/B/Y shapes and six qparams match current lowering/stage0",
                "W3 operation order and six-stage composite order match frozen contracts",
                "v36 input row-pair [0,16)+[16,32) and addresses are frozen current evidence",
            ],
            "intentional_derivation": [
                "v36 adds PE10/PE12/PE30/PE32 so FP32 add supplies 8*4B=32B",
                "v36 Load_Config uses 61 meaningful 64b words in 31 transport rows",
                "node0076 requires modulo-1000 hardware replay and 32B B padding",
            ],
            "suspected_current_defect": [
                {
                    "identity": "v35",
                    "defect": "four GA lanes supply 16B while Buffer5 requires 32B",
                    "explains_latest_return": True,
                    "status": "CLOSED_BY_V36_STATIC_CORRECTION_PENDING_DYNAMIC_RETURN",
                }
            ],
            "new_candidate_defect": [],
            "dynamic_only": [
                "v36 Buffer5 accepted 32B write",
                "v36 MSE4 request plus qualified wdata",
                "v36 split-C natural terminal",
                "v36 28/28 stage-local FP32 D exact comparison",
                "full six-stage natural terminal plus formal 28D/E3/E4/E5",
            ],
        },
        "latest_return": {
            "LAST_PROVEN_GOOD": current_v35["LAST_PROVEN_GOOD"],
            "FIRST_DIVERGENCE": current_v35["FIRST_DIVERGENCE"],
            "HANG_ROOT_CAUSE": current_v35["HANG_ROOT_CAUSE"],
            "configuration_difference_explains_current_stall": True,
        },
        "excluded_non_config_causes": [
            "historical observer clock/rate/canonical defects are not reused as v35 root cause",
            "cloud RTL identity difference is nonblocking after compile and is not proven to explain v35",
            "package transport/no-sidecar policy is unrelated to the functional stall",
        ],
    }

    ledger_doc = {
        "schema": "qlinearadd-complete-json-field-provenance-ledger-v1",
        "allowed_origins": sorted(ALLOWED_ORIGINS),
        "target_count": 17,
        "physical_stage_count": 102,
        "record_count": len(ledger),
        "unresolved_count": len(unresolved),
        "origin_counts": dict(sorted(origin_counts.items())),
        "default_state_counts": dict(sorted(default_counts.items())),
        "ordered_record_sha256": canonical_sha(
            [
                [
                    item["target_id"],
                    item["physical_stage"],
                    item["json_pointer"],
                    item["status"],
                ]
                for item in ledger
            ]
        ),
        "records": ledger,
    }
    materialization = {
        "schema": "qlinearadd-complete-strict-json-materialization-manifest-v1",
        "family": "qlinearadd",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "strict_complete_json_count": 0,
        "target_count": 17,
        "physical_stage_count": 102,
        "unresolved_required_leaf_count": len(unresolved),
        "materialization_allowed": False,
        "reason": (
            "17/17 current lowering requests reject candidate emission and the "
            "native handler capability matrix does not prove typed six-qparam "
            "transport, exact UINT8 tail, target shape adaptation, addresses, "
            "or six-stage schedule composition."
        ),
        "forbidden_fallbacks": [
            "nearest-template",
            "implicit zero/null",
            "copy current v35/v36 project JSON as upstream authority",
            "old failed package or server residue",
            "host internal tensor replay",
        ],
    }
    report = {
        "schema": "qlinearadd-complete-json-regeneration-report-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "upstream_task": "019fd276-14c5-7800-94db-87ebfb9ce632",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "family": "qlinearadd",
        "status": "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED",
        "claim_boundary": (
            "Complete logical inventory, native applicability, handler "
            "capability, planned strict-schema leaf provenance and current "
            "node0007 comparison only. No target strict hardware JSON, mapping, "
            "bitstream, execplan, SCA, package, server action or functional RTL."
        ),
        "coverage": {
            "logical_target_stages": 17,
            "physical_stages": 102,
            "structural_equivalence_classes": len(structural_classes),
            "materialized_consumer_signature_classes": len(exact_classes),
            "ledger_records": len(ledger),
            "unresolved_required_leaves": len(unresolved),
            "strict_complete_jsons": 0,
        },
        "common_blockers": [
            "B_ADD_UINT8_REQUANT",
            "B_EXECPLAN_TYPED_TRANSPORT",
        ],
        "lowering_effective_resolution": {
            hw_op: {
                "candidate_config_emission_allowed": record[
                    "candidate_config_emission_allowed"
                ],
                "effective_blockers": record["effective_blockers"],
                "formal_target_instance_allowed": record[
                    "formal_target_instance_allowed"
                ],
            }
            for hw_op, record in sorted(effective.items())
        },
        "current_config_findings": {
            "v35_config_defect_explains_latest_stall": True,
            "defect": "FP32 GA 16B supply versus Buffer5 32B required row",
            "v36_static_correction": "eight GA lanes produce 32B",
            "v36_dynamic_status": "PACKAGE_READY_NOT_RUN; no return yet",
            "other_16_targets": "cannot inherit node0007 project config as authority",
        },
        "rule_confirmation": (
            "CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001 and "
            "CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001 correctly prevent "
            "nearest-template/current-package promotion."
        ),
        "rule_delta_proposal": {
            "id": "CDA-QADD-COMPLETE-STRICT-COMPOSITE-TYPED-HANDLER-001",
            "proposal": (
                "A complete QLinearAdd strict emitter must expose one typed "
                "six-qparam composite handler covering all six physical stages, "
                "five structural shape classes including node0076 replay, "
                "per-edge address/lifetime ownership, accepted 32B buffer "
                "transactions, exact UINT8 tail and terminal. Primitive "
                "placeholders cannot satisfy any missing composite leaf."
            ),
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "current_rtl_authority": RTL_COMMIT,
        "input_receipts": {
            "lowering_bundle": {
                "path": LOWERING.relative_to(ROOT).as_posix(),
                "sha256": sha(LOWERING),
                "blob": LOWERING_BLOB,
            },
            "stage0": {
                "path": STAGE0.relative_to(ROOT).as_posix(),
                "sha256": sha(STAGE0),
                "blob": STAGE0_BLOB,
            },
            "hardware_approval": {
                "path": HARDWARE_APPROVAL.relative_to(ROOT).as_posix(),
                "sha256": sha(HARDWARE_APPROVAL),
                "blob": HARDWARE_APPROVAL_BLOB,
            },
        },
    }

    write(OUT / "stage_inventory.json", inventory)
    write(OUT / "field_provenance_ledger.json", ledger_doc)
    write(OUT / "reference_applicability.json", reference_applicability)
    write(OUT / "handler_capability.json", handler_capability)
    write(OUT / "current_test_diff.json", current_diff)
    write(OUT / "complete_json/materialization_manifest.json", materialization)
    write(OUT / "report.json", report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "targets": 17,
                "physical_stages": 102,
                "structural_classes": len(structural_classes),
                "exact_signature_classes": len(exact_classes),
                "ledger_records": len(ledger),
                "unresolved": len(unresolved),
                "strict_jsons": 0,
                "output": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
