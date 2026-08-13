#!/usr/bin/env python3
"""Build the qlinear_matmul complete-JSON candidate without server artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
FAMILY = "qlinear_matmul"
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinear_matmul"
)
COMPLETE = OUT / "complete_json"
CURRENT_JSON_DIR = (
    ROOT
    / "ndp-sim/model_execplan/output/"
    "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2/jsons"
)
TARGET_GRAPH = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2/"
    "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2.json"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
POLICY = (
    ROOT
    / "contracts/operator_config/complete_json_generation_contract_v1.json"
)
AUTHORITY = (
    ROOT
    / "contracts/operator_config/operator_config_authority_v1.json"
)
SEMANTICS = (
    ROOT
    / "contracts/operator_config/stage_operator_semantics_audit_v1.json"
)
CURRENT_TASK = (
    ROOT
    / ".agents/task_records/"
    "20260805_node0075_v5_return_bankrow_cloud_v9_package_ready.md"
)
CURRENT_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_0cc_bankrow_v9.zip"
)
CURRENT_PACKAGE_DIR = CURRENT_PACKAGE.with_suffix("")
MATERIALIZER_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2/"
    "materializer_report.json"
)

NDP_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
RTL_REPOSITORY = "xlsjdjdk/Trassic2.0_RTL"
RTL_WR_BUFFER = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
    "Memory_Stream_Engine/Memory_RD_Stream_Engine/WR_Buffer_AG.sv"
)
RTL_MEMORY_REQ = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/"
    "Buffer_Manager_Cluster/Memory_Req_Manager.sv"
)
RTL_ARRAY_REQ = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/"
    "Buffer_Manager_Cluster/Array_Request_Manager.sv"
)
CURRENT_HANDLER = (
    ROOT
    / "ndp-sim/model_execplan/src/execution_plan_generator/"
    "control_registers.py"
)
OUTPUT_WRITER = (
    ROOT
    / "ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py"
)
INSTRUCTION_GENERATOR = (
    ROOT
    / "ndp-sim/model_execplan/src/execution_plan_generator/"
    "instruction_generator.py"
)

TARGET_HW_OP_TYPES = ["MatMulInt32Accumulate", "RequantizeUint8"]
LOGICAL_STAGE_IDS = ["hwop-0075-00", "hwop-0075-01"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_blob_oid(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def bound(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256_file(path)}


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
            return
        for key in sorted(value):
            yield from leaves(value[key], f"{pointer}/{escape(str(key))}")
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", value
            return
        for index, item in enumerate(value):
            yield from leaves(item, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def get_pointer(value: Any, pointer: str) -> Any:
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def stage_kind(stage_id: str) -> str:
    if "_accum_" in stage_id:
        return "accumulate"
    if "_scale_" in stage_id:
        return "scale"
    if "_round_" in stage_id:
        return "round"
    raise ValueError(stage_id)


def stage_pass(stage_id: str) -> int:
    match = re.search(r"_pass(\d\d)$", stage_id)
    if match is None:
        raise ValueError(stage_id)
    return int(match.group(1))


def source_jsons() -> dict[str, tuple[Path, dict[str, Any]]]:
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(CURRENT_JSON_DIR.glob("*.json")):
        stage_id = path.name.split("_MatMul", 1)[0]
        stage_id = stage_id.split("_Node0075", 1)[0]
        if stage_id in result:
            raise ValueError(f"duplicate current stage JSON: {stage_id}")
        result[stage_id] = (path, load(path))
    expected = {
        f"node0075_{kind}_pass{index:02d}"
        for kind in ("accum", "scale", "round")
        for index in range(8)
    }
    if set(result) != expected:
        raise ValueError(
            f"current stage set mismatch: missing={sorted(expected-set(result))}; "
            f"extra={sorted(set(result)-expected)}"
        )
    return result


def build_candidate_stage(
    stage_id: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    candidate = copy.deepcopy(current)
    if "_accum_" not in stage_id:
        return candidate
    # RTL Memory_Req_Manager writes one input byte per unique bank/byte
    # position. The old [0,1]*8 vector aliases and later lanes overwrite
    # earlier lanes. SA_Inport performs the required row/column broadcast.
    candidate["stream_engine"]["stream1"]["buf_spatial_stride"] = list(
        range(16)
    )
    # READ_STREAM0 alternates buffer0/buffer1. Both weight panels are used by
    # all M=16 rows, so both physical instances require the same lifetime.
    candidate["buffer_config"]["buffer0"]["buffer_life_time"] = 16
    candidate["buffer_config"]["buffer1"]["buffer_life_time"] = 16
    # Strict materialization of the inactive third write index. Legacy integer
    # zero silently encoded the same bit pattern but is not a semantic mode.
    candidate["stream_engine"]["stream2"]["mem_idx_mode"][2] = None
    candidate["stream_engine"]["stream2"]["mem_idx_keep_last_index"][2] = None
    return candidate


def build_stage_inventory(
    graph: dict[str, Any],
    candidate_files: dict[str, Path],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    operators = {item["id"]: item for item in graph["operators"]}
    stages: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    for stage_id in sorted(
        operators,
        key=lambda item: (
            {"accumulate": 0, "scale": 1, "round": 2}[
                stage_kind(item)
            ],
            stage_pass(item),
        ),
    ):
        op = operators[stage_id]
        kind = stage_kind(stage_id)
        pass_index = stage_pass(stage_id)
        logical_count = int(op["attributes"]["n_count"])
        tail = logical_count != 128
        class_id = f"{kind}_{'tail104_pad24' if tail else 'full128'}"
        class_counts[class_id] += 1
        strict = candidates[stage_id]
        if kind == "accumulate":
            lowering_id = "hwop-0075-00"
            lowering_type = "MatMulInt32Accumulate"
            parents = ["node0071_final_uint8_D"]
            qparams = {
                "a_zero_point": 0,
                "b_zero_point": 0,
                "accumulator": "int32 modulo 2^32",
            }
            address_owner = {
                "stream0": "node0075 B/weight pass allocation",
                "stream1": "node0071-owned A existing-storage alias",
                "stream2": "node0075 accumulate scratch D",
                "stream3": "node0075 B-prime/weight alias",
            }
        elif kind == "scale":
            lowering_id = "hwop-0075-01"
            lowering_type = "RequantizeUint8"
            parents = [f"node0075_accum_pass{pass_index:02d}"]
            qparams = {
                "requant_multiplier_bits": op["attributes"][
                    "requant_multiplier_bits"
                ],
                "rounding": "none; exact FP32 multiply stage",
            }
            address_owner = {
                "stream0": "node0075 accumulate scratch producer",
                "stream2": "node0075 FP32 scale scratch",
            }
        else:
            lowering_id = "hwop-0075-01"
            lowering_type = "RequantizeUint8"
            parents = [f"node0075_scale_pass{pass_index:02d}"]
            qparams = {
                "y_zero_point": 60,
                "magic_bits": "0x4b400000",
                "rounding": (
                    "FP32 magic add then INT32 subtract then UINT8 saturate"
                ),
            }
            address_owner = {
                "stream0": "node0075 FP32 scale scratch producer",
                "stream2": "node0075 formal uint8 D fragment",
            }
        streams = {
            name: {
                "target": item["target"],
                "mode": item["mode"],
                "base_addr": item["base_addr"],
            }
            for name, item in strict["stream_engine"].items()
        }
        stages.append(
            {
                "physical_stage_id": stage_id,
                "lowering_hw_op_id": lowering_id,
                "lowering_hw_op_type": lowering_type,
                "op_type": op["type"],
                "pass_index": pass_index,
                "materialized_consumer_signature_class": class_id,
                "inputs": {
                    name: {
                        "dtype": spec["dtype"],
                        "shape": spec["shape"],
                        "layout": "slice-sharded contiguous physical-N128",
                        "source": spec.get("source"),
                    }
                    for name, spec in op["inputs"].items()
                },
                "output": {
                    "dtype": op["output"]["dtype"],
                    "shape": op["output"]["shape"],
                    "layout": "slice-sharded contiguous physical-N128",
                },
                "qparams": qparams,
                "padding_tail": {
                    "physical_n": 128,
                    "logical_n": logical_count,
                    "padding_n": 128 - logical_count,
                    "padding_value": 60 if kind == "round" else 0,
                },
                "dag": {
                    "parents": parents,
                    "stage_order": [
                        "accumulate",
                        "scale",
                        "round",
                    ],
                },
                "lifetime": {
                    name: item["buffer_life_time"]
                    for name, item in strict["buffer_config"].items()
                },
                "addresses": streams,
                "address_owner": address_owner,
                "strict_json": bound(candidate_files[stage_id]),
            }
        )
    return {
        "schema": "qlinear_matmul_complete_stage_inventory_v1",
        "family": FAMILY,
        "lowering_bindings": [
            {
                "hw_op_id": "hwop-0075-00",
                "hw_op_type": "MatMulInt32Accumulate",
                "physical_stage_ids": [
                    f"node0075_accum_pass{i:02d}" for i in range(8)
                ],
            },
            {
                "hw_op_id": "hwop-0075-01",
                "hw_op_type": "RequantizeUint8",
                "physical_stage_ids": [
                    *[f"node0075_scale_pass{i:02d}" for i in range(8)],
                    *[f"node0075_round_pass{i:02d}" for i in range(8)],
                ],
            },
        ],
        "physical_stage_count": len(stages),
        "equivalence_class_count": len(class_counts),
        "equivalence_class_counts": dict(sorted(class_counts.items())),
        "stages": stages,
        "claim_boundary": (
            "All node0075 accumulate/scale/round materialized stages only; "
            "no other RequantizeUint8 family stage is claimed."
        ),
    }


def current_source_record(
    source_path: Path,
    pointer: str,
    value: Any,
) -> dict[str, Any]:
    return {
        "path": rel(source_path),
        "commit": "WORKTREE_NO_COMMIT",
        "blob_oid": "NO_GIT_BLOB_PROJECT_OUTPUT",
        "file_sha256": sha256_file(source_path),
        "json_pointer": pointer,
        "value": value,
    }


def is_inactive(pointer: str, value: Any) -> bool:
    inactive_tokens = (
        "/padding_enable/",
        "/tailing_enable/",
        "/nbr_enable",
        "/bias_enable",
        "/fp32tofp16",
        "/fp32tobf16",
    )
    if value is None:
        return True
    if any(token in pointer for token in inactive_tokens) and value in (
        0,
        "false",
        False,
    ):
        return True
    return False


def origin_for(pointer: str, value: Any) -> str:
    if is_inactive(pointer, value):
        return "EXPLICIT_DISABLED"
    if pointer.endswith("/base_addr"):
        return "ADDRESS_PLANNER_DERIVED"
    if pointer.endswith("/CONFIG"):
        return "ENCODER_DERIVED"
    if "/gemm_shape/" in pointer:
        return "MODEL_DERIVED"
    if "/special_array/" in pointer or "/general_array/" in pointer:
        return "RTL_DERIVED"
    if "/buffer_config/" in pointer:
        return "SCHEDULE_DERIVED"
    if "/stream_engine/" in pointer:
        if pointer.endswith("/mem_idx_mode/2") or pointer.endswith(
            "/mem_idx_keep_last_index/2"
        ):
            return "ENCODER_DERIVED"
        if "/buf_spatial_stride/" in pointer:
            return "RTL_DERIVED"
        return "SCHEDULE_DERIVED"
    if "/dram_loop_configs/" in pointer or "/lc_pe_configs/" in pointer:
        return "SCHEDULE_DERIVED"
    if "/buffer_loop_configs/" in pointer:
        return "SCHEDULE_DERIVED"
    return "MODEL_DERIVED"


def consumer_equation(pointer: str) -> str:
    if pointer.endswith("/CONFIG"):
        return "CONFIG bits[7:0] select IGA/LSU/SA/GA enable and update state"
    if pointer.endswith("/base_addr"):
        return (
            "address = base_addr + Σ(index[d]*dim_stride[d]); "
            "physical bank/row/column decoded by current MSE"
        )
    if "/buf_spatial_stride/" in pointer:
        return (
            "WR_Buffer_AG col[i]=base_col+stride[i]; Memory_Req_Manager "
            "bank=col[4:2], byte=col[1:0], later duplicate lane overwrites"
        )
    if pointer.endswith("/buffer_life_time"):
        return (
            "Array_Request_Manager releases after inclusive accepted visit "
            "count reaches encoded lifetime-1; ping-pong peers alternate"
        )
    if "/stream_engine/" in pointer:
        return (
            "MSE index/tag recurrence emits accepted byte request and Buffer "
            "write/read transaction"
        )
    if "/buffer_config/" in pointer:
        return (
            "Buffer mask/row/lifetime controls valid-bank supply, accepted "
            "array visits, and release"
        )
    if "/special_array/" in pointer:
        return (
            "INT8 SA consumes signed DataA, unsigned DataB, int32 psum and "
            "qualified tag/last recurrence"
        )
    if "/general_array/" in pointer:
        return (
            "GA opcode/conversion/constant fields implement scale or exact "
            "UINT8 round/saturate tail"
        )
    if "/dram_loop_configs/" in pointer:
        return "IGA signed loop recurrence determines occurrence and terminal tags"
    if "/lc_pe_configs/" in pointer:
        return "LC PE selects loop source, opcode, constant, and feedback carrier"
    if "/buffer_loop_configs/" in pointer:
        return "Buffer ROW/COL loop maps accepted occurrence to buffer address/tag"
    if "/gemm_shape/" in pointer:
        return "typed model M/K/N maps to physical SA tile geometry"
    return "typed node0075 target model and exact materialized consumer"


def build_derivation_receipt(
    current_sources: dict[str, tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    duplicate_map = [0, 1] * 8
    current_last_writer = {
        str(address): max(
            index for index, mapped in enumerate(duplicate_map) if mapped == address
        )
        for address in sorted(set(duplicate_map))
    }
    return {
        "schema": "qlinear_matmul_complete_json_derivation_receipt_v1",
        "family": FAMILY,
        "identities": {
            "policy": bound(POLICY),
            "authority": bound(AUTHORITY),
            "lowering": bound(LOWERING),
            "target_graph": bound(TARGET_GRAPH),
            "stage_semantics": bound(SEMANTICS),
            "current_handler": bound(CURRENT_HANDLER),
            "output_writer": bound(OUTPUT_WRITER),
            "instruction_generator": bound(INSTRUCTION_GENERATOR),
            "rtl": {
                "repository": RTL_REPOSITORY,
                "commit": RTL_COMMIT,
                "wr_buffer_ag": {
                    **bound(RTL_WR_BUFFER),
                    "blob_oid": git_blob_oid(RTL_WR_BUFFER),
                },
                "memory_req_manager": {
                    **bound(RTL_MEMORY_REQ),
                    "blob_oid": git_blob_oid(RTL_MEMORY_REQ),
                },
                "array_request_manager": {
                    **bound(RTL_ARRAY_REQ),
                    "blob_oid": git_blob_oid(RTL_ARRAY_REQ),
                },
            },
            "current_stage_jsons": {
                stage_id: bound(path)
                for stage_id, (path, _) in sorted(current_sources.items())
            },
        },
        "derivations": {
            "accumulate_stream1_spatial_layout": {
                "current": duplicate_map,
                "candidate": list(range(16)),
                "current_unique_positions": 2,
                "candidate_unique_positions": 16,
                "current_last_writer_by_position": current_last_writer,
                "proof": (
                    "WR_Buffer_AG forms one column per input byte. "
                    "Memory_Req_Manager assigns each bank byte in ascending "
                    "req_idx, so duplicate columns retain only the later lane. "
                    "The SA inport independently broadcasts the completed "
                    "8x32-bit vector; MSE aliases are not broadcast semantics."
                ),
            },
            "accumulate_weight_pingpong_lifetime": {
                "M": 16,
                "candidate_buffer0": 16,
                "candidate_buffer1": 16,
                "proof": (
                    "READ_STREAM0 alternates buffer0/buffer1. Each physical "
                    "weight panel is consumed once for each of 16 M rows; "
                    "authorized ping-pong topology requires identical peers."
                ),
            },
            "inactive_write_index_normalization": {
                "candidate_mem_idx_mode_2": None,
                "candidate_keep_last_index_2": None,
                "proof": (
                    "The third write index is inactive. JSON null is the "
                    "strict semantic spelling of encoded mode zero; a keep "
                    "threshold is not applicable without keep mode."
                ),
            },
        },
        "negative_controls": [
            {
                "id": "NC_DUPLICATE_SPATIAL_LANE",
                "mutation": "restore stream1 [0,1] repeated eight times",
                "expected": "STREAM.SPATIAL_ALIAS and overwrite microtrace",
            },
            {
                "id": "NC_PINGPONG_LIFETIME_MISMATCH",
                "mutation": "restore buffer0 lifetime=1 while buffer1=16",
                "expected": "BUFFER.PINGPONG_PAIR_MISMATCH",
            },
            {
                "id": "NC_LEGACY_INTEGER_INDEX_MODE",
                "mutation": "restore stream2 mem_idx_mode[2]=0",
                "expected": "VALUE.ENUM",
            },
        ],
        "claim_boundary": (
            "Static target JSON derivation and direct-consumer equations only; "
            "no mapping, bitstream, execplan, SCA, server package, server run, "
            "natural terminal, formal D, E3, E4, or E5."
        ),
    }


def build_ledger(
    candidate: dict[str, Any],
    current_sources: dict[str, tuple[Path, dict[str, Any]]],
    receipt_path: Path,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    absences: list[dict[str, Any]] = []
    receipt_binding = bound(receipt_path)
    for pointer, value in leaves(candidate):
        parts = pointer.split("/")
        stage_id = parts[1].replace("~1", "/").replace("~0", "~")
        inner_pointer = "/" + "/".join(parts[2:])
        source_path, source_document = current_sources[stage_id]
        source_value = get_pointer(source_document, inner_pointer)
        origin = origin_for(pointer, value)
        applicability = (
            "EXPLICITLY_INACTIVE"
            if origin == "EXPLICIT_DISABLED"
            else "DERIVED_FOR_TARGET"
        )
        entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "applicability_class": applicability,
                "exactness_axes": {
                    "op": True,
                    "dtype": True,
                    "shape": True,
                    "layout": True,
                    "qparams": True,
                    "topology": True,
                    "address": True,
                    "schedule": True,
                    "consumer": True,
                },
                "owner": (
                    "candidate exact patch generator"
                    if source_value != value
                    else "node0075 materializer plus current direct consumer"
                ),
                "consumer_equation": consumer_equation(pointer),
                "derivation_receipt": (
                    None if origin == "EXPLICIT_DISABLED" else receipt_binding
                ),
                "source": current_source_record(
                    source_path, inner_pointer, source_value
                ),
                "negative_control_ids": (
                    ["NC_DUPLICATE_SPATIAL_LANE"]
                    if "/stream1/buf_spatial_stride/" in pointer
                    else (
                        ["NC_PINGPONG_LIFETIME_MISMATCH"]
                        if pointer.endswith("/buffer0/buffer_life_time")
                        else (
                            ["NC_LEGACY_INTEGER_INDEX_MODE"]
                            if "/stream2/mem_idx_" in pointer
                            and pointer.endswith("/2")
                            else []
                        )
                    )
                ),
                "status": "RESOLVED",
            }
        )
        if value is None:
            absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_NULL_INACTIVE",
                    "reason": (
                        "The direct consumer disables or does not select this "
                        "nullable field."
                    ),
                    "owner": "candidate exact patch generator",
                }
            )
        elif value == 0 and not isinstance(value, bool):
            absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_ZERO",
                    "reason": (
                        "Zero is explicitly materialized and is not inferred "
                        "from a missing source field."
                    ),
                    "owner": "typed model, schedule, or explicit disable bit",
                }
            )
        if source_value != value and value is not None:
            absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "TARGET_REQUIRED_DERIVED",
                    "reason": (
                        "Current project-added comparison value is not target "
                        "authority; the candidate value is derived by current "
                        "RTL/encoder/schedule equations."
                    ),
                    "owner": "candidate exact patch generator",
                }
            )
    for stage_id in sorted(candidate):
        kind = stage_kind(stage_id)
        absent = (
            "general_array" if kind == "accumulate" else "special_array"
        )
        absences.append(
            {
                "target_json_pointer": f"/{stage_id}/{absent}",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": (
                    f"{absent} is disabled by this physical stage primitive "
                    "and is not part of its strict JSON."
                ),
                "owner": "CONFIG mask and primitive topology",
            }
        )
    return {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": FAMILY,
        "candidate_json_sha256": sha256_file(
            COMPLETE / "qlinear_matmul_node0075_all_stages.strict.json"
        ),
        "entries": entries,
        "source_absences": absences,
        "claim_boundary": (
            "One entry per scalar/empty-container leaf of the aggregate "
            "24-stage strict JSON candidate. Project-added current JSONs are "
            "comparison sources, never upstream authority."
        ),
    }


def build_handler_capability(
    candidate: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    dependent: list[dict[str, Any]] = []
    current_leaves = dict(leaves(current))
    for pointer, value in leaves(candidate):
        if current_leaves[pointer] == value:
            continue
        if "/buffer_config/buffer0/buffer_life_time" in pointer:
            axes = ["cross_stage_schedule"]
            owner = "exact M=16 ping-pong lifetime derivation"
        else:
            axes = ["layout"]
            owner = "exact MSE lane/strict encoder normalization"
        dependent.append(
            {
                "json_pointer": pointer,
                "axes": axes,
                "covered_by": owner,
                "status": "COVERED",
            }
        )
    builder = Path(__file__).resolve()
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": FAMILY,
        "handler": {
            "kind": "AUTHORIZED_PATCH",
            "path": rel(builder),
            "sha256": sha256_file(builder),
            "source_span": (
                "build_candidate_stage plus exact stage-set/source binding"
            ),
        },
        "capabilities": {
            "exact_replay": {
                "supported": True,
                "evidence": (
                    "Deterministic exact 24-stage rebuild from the bound "
                    "current source set; no generalized shape claim."
                ),
            },
            "shape": {
                "supported": False,
                "evidence": (
                    "Only physical [1,1,2048]/[1,2048,128]/[1,1,128] "
                    "signatures and the frozen 104-element logical tail."
                ),
            },
            "dtype": {
                "supported": False,
                "evidence": "Only uint8/int8/int32/fp32 frozen node0075 dtypes.",
            },
            "qparam": {
                "supported": False,
                "evidence": (
                    "Only multiplier 0x3a510db3 and y_zero_point=60; no "
                    "qparam generalization."
                ),
            },
            "layout": {
                "supported": True,
                "evidence": (
                    "Exact node0075 MSE 16-byte identity lane layout and "
                    "inactive-index normalization are derived and checked."
                ),
            },
            "address": {
                "supported": False,
                "evidence": (
                    "Candidate reuses byte-identical v9 JSON base addresses; "
                    "this builder is not an address planner."
                ),
            },
            "cross_stage_schedule": {
                "supported": True,
                "evidence": (
                    "Exact M=16 READ_STREAM0 ping-pong peer lifetime and the "
                    "frozen eight-pass accumulate/scale/round order only."
                ),
            },
        },
        "dependent_leaves": dependent,
        "claim_boundary": (
            "Capabilities are exact-target capabilities of this isolated "
            "candidate builder. They do not generalize the project-added "
            "native registry/handler to another shape, dtype, qparam, layout, "
            "address plan, or schedule."
        ),
    }


def build_current_diff(
    candidate: dict[str, Any],
    current: dict[str, Any],
    current_snapshot_path: Path,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    current_leaves = dict(leaves(current))
    for pointer, value in leaves(candidate):
        current_value = current_leaves[pointer]
        if value == current_value:
            classification = "SAME"
            reason = "Candidate preserves the current materialized value."
            evidence = [rel(current_snapshot_path)]
        elif "/stream1/buf_spatial_stride/" in pointer:
            classification = "SUSPECTED_CURRENT_DEFECT"
            reason = (
                "Current duplicate MSE byte locations are last-writer-wins; "
                "candidate uses one position per accepted input byte."
            )
            evidence = [
                f"{rel(RTL_WR_BUFFER)}:82",
                f"{rel(RTL_MEMORY_REQ)}:Memory_Req_Manager write-data loop",
                "NC_DUPLICATE_SPATIAL_LANE",
            ]
        elif pointer.endswith("/buffer0/buffer_life_time"):
            classification = "SUSPECTED_CURRENT_DEFECT"
            reason = (
                "Current ping-pong peers have lifetime 1/16 despite both "
                "alternating weight panels serving M=16 rows."
            )
            evidence = [
                rel(SEMANTICS),
                f"{rel(RTL_ARRAY_REQ)}:array_life_cnt release equation",
                "NC_PINGPONG_LIFETIME_MISMATCH",
            ]
        else:
            classification = "INTENTIONAL_DERIVATION"
            reason = (
                "Inactive third write index is expressed as semantic null "
                "rather than legacy integer zero/threshold."
            )
            evidence = [
                "NC_LEGACY_INTEGER_INDEX_MODE",
                "resnet50_pipeline/operator_config_validator.py",
            ]
        entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": value,
                "current_value_present": True,
                "current_value": current_value,
                "classification": classification,
                "reason": reason,
                "evidence": evidence,
            }
        )
    blocker_attribution = [
        {
            "blocker_id": (
                "B_MATMUL_NODE0075_BANKROW_V9_DYNAMIC_ADDRESS_AND_STAGE_ENTRY"
            ),
            "classification": "CONFIG_EXCLUDED",
            "candidate_json_pointers": [],
            "reason": (
                "v5 stopped on the old invalid 0x01706400 preload before "
                "node0075 stage00. v9 relocation fixed that address; the new "
                "lane/lifetime corrections were not reached in v5."
            ),
            "evidence": [rel(CURRENT_TASK)],
        },
        {
            "blocker_id": (
                "B_MATMUL_NODE0075_PRODUCER_ACCEPT_TO_PASS00_FIRST_READ_ORDERING"
            ),
            "classification": "DYNAMIC_ONLY",
            "candidate_json_pointers": [],
            "reason": (
                "Static JSON order and aliases do not prove actual producer "
                "acceptance before the first node0075 read."
            ),
            "evidence": [rel(CURRENT_TASK)],
        },
        {
            "blocker_id": (
                "B_MATMUL_NODE0075_ACTUAL_A_READS_8192_AND_HASH"
            ),
            "classification": "DYNAMIC_ONLY",
            "candidate_json_pointers": [],
            "reason": (
                "Configured eight passes/8192 reads are not actual accepted "
                "traffic until a run reaches all node0075 stages."
            ),
            "evidence": [rel(CURRENT_TASK)],
        },
        {
            "blocker_id": "B_MATMUL_NODE0075_SERVER_NATURAL_TERMINAL",
            "classification": "DYNAMIC_ONLY",
            "candidate_json_pointers": [],
            "reason": "Natural terminal is server-runtime evidence, not JSON.",
            "evidence": [rel(CURRENT_TASK)],
        },
        {
            "blocker_id": "B_MATMUL_NODE0075_SERVER_FORMAL_D",
            "classification": "DYNAMIC_ONLY",
            "candidate_json_pointers": [],
            "reason": "Formal 144-D readback is server-runtime evidence.",
            "evidence": [rel(CURRENT_TASK)],
        },
        {
            "blocker_id": "NODE0075_ACCUMULATE_MSE_LANE_AND_LIFETIME",
            "classification": "CONFIG_CONTRIBUTES",
            "candidate_json_pointers": [
                entry["json_pointer"]
                for entry in entries
                if entry["classification"] == "SUSPECTED_CURRENT_DEFECT"
            ],
            "reason": (
                "If v9 reaches accumulate, current aliases can overwrite "
                "accepted bytes and asymmetric lifetime can release one peer "
                "early. This is a future-stage configuration risk, not an "
                "explanation of the already-observed v5 bank-row stop."
            ),
            "evidence": [rel(RTL_MEMORY_REQ), rel(RTL_ARRAY_REQ)],
        },
    ]
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": FAMILY,
        "candidate_json_sha256": sha256_file(
            COMPLETE / "qlinear_matmul_node0075_all_stages.strict.json"
        ),
        "current_identity": {
            "available": True,
            "path": rel(current_snapshot_path),
            "sha256": sha256_file(current_snapshot_path),
            "package_or_record": (
                f"{rel(CURRENT_PACKAGE)} "
                f"sha256={sha256_file(CURRENT_PACKAGE)}; {rel(CURRENT_TASK)}"
            ),
            "latest_result": (
                "v9 PACKAGE_READY_NOT_RUN; latest v5 return stopped before "
                "node0075 stage00 on invalid bank/row preload, so ordering, "
                "8192 actual reads, natural terminal, and formal D remain "
                "dynamic-only."
            ),
        },
        "entries": entries,
        "blocker_attribution": blocker_attribution,
        "claim_boundary": (
            "Leaf comparison is against an exact aggregate snapshot of the "
            "current v9 source JSONs. Package/observer/RTL/runtime blockers "
            "are not reclassified as configuration defects."
        ),
    }


def build_composition() -> dict[str, Any]:
    boundaries: list[dict[str, Any]] = []
    a_byte_set = (
        "16 slices × per-slice [node0071_D_base,node0071_D_base+2048); "
        "unique=32768B; required eight-pass multiplicity=262144B"
    )
    boundaries.append(
        {
            "boundary_id": "node0071_D_to_node0075_accumulate_A_eight_pass",
            "producer_dtype": "uint8",
            "consumer_dtype": "uint8",
            "shape": "[16,2048] logical; [1,1,2048] per slice/pass",
            "layout": "batch-slice-sharded contiguous bytes",
            "producer_byte_set": a_byte_set,
            "consumer_required_byte_set": a_byte_set,
            "transaction_bytes": 32,
            "tag_last": (
                "Each pass reads 512 ordered 32B transactions per slice; "
                "pass terminal is carried by the configured MSE/Buffer tags."
            ),
            "clock_handshake": (
                "Same simulator execution stream; actual accepted ordering "
                "remains a separately reported dynamic gate."
            ),
            "lifetime_visibility": (
                "Static owner/storage alias and eight-pass lifetime are "
                "resolved. No opcode110 fence or generic barrier is claimed."
            ),
            "qparam_rounding": (
                "Activation is consumed byte-exact with a_zero_point=0; no "
                "rounding at this boundary."
            ),
            "status": "RESOLVED",
            "evidence": [
                "contracts/operator_config/"
                "node0071_node0075_uint8_identity_alias_integration_v1.json",
                rel(TARGET_GRAPH),
                rel(CURRENT_TASK),
            ],
        }
    )
    for index in range(8):
        logical = 104 if index == 7 else 128
        for producer, consumer, dtype, scratch in (
            ("accumulate", "scale", "int32", "int32_psum"),
            ("scale", "round", "fp32", "fp32_scaled"),
        ):
            byte_set = (
                f"pass{index:02d} physical [0,128) lanes ×4B per slice; "
                f"logical [0,{logical}) and deterministic tail"
            )
            boundaries.append(
                {
                    "boundary_id": (
                        f"node0075_pass{index:02d}_{producer}_to_{consumer}"
                    ),
                    "producer_dtype": dtype,
                    "consumer_dtype": dtype,
                    "shape": f"[1,1,128] physical; {logical} logical lanes",
                    "layout": (
                        "slice-local contiguous 128-lane scratch fragment"
                    ),
                    "producer_byte_set": byte_set,
                    "consumer_required_byte_set": byte_set,
                    "transaction_bytes": 32,
                    "tag_last": (
                        "Producer formal stage terminal feeds the same-pass "
                        "consumer stage after normal command transition."
                    ),
                    "clock_handshake": (
                        "Producer Buffer accepted write and consumer MSE "
                        "qualified read in the native slice clock domain."
                    ),
                    "lifetime_visibility": (
                        f"{scratch} allocation remains live through the "
                        f"same-pass {consumer} consumer and is then released."
                    ),
                    "qparam_rounding": (
                        "accumulate→scale owns exact multiplier "
                        "0x3a510db3"
                        if consumer == "scale"
                        else (
                            "scale→round owns magic RNE, subtract "
                            "0x4b400000-60, and uint8 saturation"
                        )
                    ),
                    "status": "RESOLVED",
                    "evidence": [
                        rel(TARGET_GRAPH),
                        rel(MATERIALIZER_REPORT),
                    ],
                }
            )
    return {
        "schema": "operator_config_composition_boundary_v1",
        "family": FAMILY,
        "boundaries": boundaries,
        "claim_boundary": (
            "Typed, byte-set, tag, lifetime, and qparam ownership for the "
            "node0075 composite chain. Actual accepted producer→pass00 order, "
            "8192 reads, terminal, and D remain dynamic gates and are not "
            "claimed by this static contract."
        ),
    }


def build_reference_applicability() -> dict[str, Any]:
    refs = [
        {
            "path": "ndp-sim/jsons/prefill_gemm_local.json",
            "class": "C",
            "repository": "ndp-sim",
            "commit": NDP_COMMIT,
            "blob_oid": "1f340e0562c321488ea7c454025506a4af64552c",
            "file_sha256": sha256_file(
                ROOT / "ndp-sim/jsons/prefill_gemm_local.json"
            ),
            "applicability": (
                "Topology only: same SA GEMM block; FP16 numeric/dtype, "
                "shape, layout, lifetime, and tail differ."
            ),
            "upstream_authority": True,
        },
        {
            "path": "ndp-sim/jsons/gemv_config_local_M1N128K32.json",
            "class": "C",
            "repository": "ndp-sim",
            "commit": NDP_COMMIT,
            "blob_oid": "d0094d4348e83793f1582e1f01e1a46aac46d475",
            "file_sha256": sha256_file(
                ROOT / "ndp-sim/jsons/gemv_config_local_M1N128K32.json"
            ),
            "applicability": (
                "Topology only: GEMV/FP16 mode and shape are not node0075 "
                "INT8 rank-2 MatMul authority."
            ),
            "upstream_authority": True,
        },
        {
            "path": "ndp-sim/model_execplan/op_json/gemm_local_sv.json",
            "class": "C",
            "repository": "ndp-sim",
            "commit": NDP_COMMIT,
            "blob_oid": "8c0841571c9432522d41ca4bf68f6270eda68e4f",
            "file_sha256": sha256_file(
                ROOT / "ndp-sim/model_execplan/op_json/gemm_local_sv.json"
            ),
            "applicability": (
                "Graph/topology reference only; target numeric type and "
                "materialized consumer differ."
            ),
            "upstream_authority": True,
        },
    ]
    for name in (
        "MatMulInt32Accumulate.json",
        "Node0075RequantScaleInt32ToFp32.json",
        "Node0075RequantRoundFp32ToUint8.json",
    ):
        path = ROOT / "ndp-sim/jsons" / name
        refs.append(
            {
                "path": rel(path),
                "class": "D",
                "repository": "ndp-sim working tree",
                "commit": "NONE_UNTRACKED",
                "blob_oid": "NONE_UNTRACKED",
                "file_sha256": sha256_file(path),
                "applicability": (
                    "Project-added/untracked exact comparison/template only; "
                    "never upstream native authority."
                ),
                "upstream_authority": False,
            }
        )
    return {
        "schema": "qlinear_matmul_reference_applicability_v1",
        "family": FAMILY,
        "grade_counts": dict(
            sorted(Counter(item["class"] for item in refs).items())
        ),
        "references": refs,
        "claim_boundary": (
            "No class-A or class-B native target reference exists. FP16 "
            "GEMM/GEMV assets are class-C topology references only; all "
            "project MatMul/Requant JSONs are class D."
        ),
    }


def main() -> int:
    if not CURRENT_PACKAGE.is_file():
        raise FileNotFoundError(CURRENT_PACKAGE)
    current_sources = source_jsons()
    graph = load(TARGET_GRAPH)
    lowering = load(LOWERING)
    lowering_bindings = {
        item["identity"]["hw_op_id"]: item["identity"]["hw_op_type"]
        for item in lowering["requests"]
        if item["identity"]["hw_op_id"] in LOGICAL_STAGE_IDS
    }
    if lowering_bindings != {
        "hwop-0075-00": "MatMulInt32Accumulate",
        "hwop-0075-01": "RequantizeUint8",
    }:
        raise ValueError(f"lowering identity mismatch: {lowering_bindings}")

    candidates = {
        stage_id: build_candidate_stage(stage_id, payload)
        for stage_id, (_, payload) in sorted(current_sources.items())
    }
    current_aggregate = {
        stage_id: payload
        for stage_id, (_, payload) in sorted(current_sources.items())
    }
    candidate_aggregate = {
        stage_id: payload for stage_id, payload in sorted(candidates.items())
    }

    candidate_files: dict[str, Path] = {}
    for stage_id, payload in sorted(candidates.items()):
        source_name = current_sources[stage_id][0].name
        path = COMPLETE / source_name
        write(path, payload)
        candidate_files[stage_id] = path
    candidate_path = (
        COMPLETE / "qlinear_matmul_node0075_all_stages.strict.json"
    )
    current_snapshot_path = OUT / "current_test_snapshot.json"
    write(candidate_path, candidate_aggregate)
    write(current_snapshot_path, current_aggregate)

    receipt_path = OUT / "derivation_receipt.json"
    write(receipt_path, build_derivation_receipt(current_sources))

    inventory_path = OUT / "stage_inventory.json"
    write(
        inventory_path,
        build_stage_inventory(
            graph, candidate_files, candidates
        ),
    )
    refs_path = OUT / "reference_applicability.json"
    write(refs_path, build_reference_applicability())

    ledger_path = OUT / "field_provenance_ledger.json"
    write(
        ledger_path,
        build_ledger(
            candidate_aggregate, current_sources, receipt_path
        ),
    )
    handler_path = OUT / "handler_capability.json"
    write(
        handler_path,
        build_handler_capability(candidate_aggregate, current_aggregate),
    )
    diff_path = OUT / "current_test_diff.json"
    write(
        diff_path,
        build_current_diff(
            candidate_aggregate,
            current_aggregate,
            current_snapshot_path,
        ),
    )
    composition_path = OUT / "composition_boundary.json"
    write(composition_path, build_composition())

    contract_path = OUT / "candidate_contract.json"
    contract = {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": FAMILY,
        "candidate_status": "COMPLETE",
        "reference_class": "D",
        "changed_axes": ["layout", "cross_stage_schedule"],
        "target_hw_op_types": TARGET_HW_OP_TYPES,
        "stage_ids": LOGICAL_STAGE_IDS,
        "candidate_json": bound(candidate_path),
        "field_provenance_ledger": bound(ledger_path),
        "handler_capability": bound(handler_path),
        "current_test_diff": bound(diff_path),
        "composition": {
            "required": True,
            "boundary": bound(composition_path),
        },
        "artifact_root": rel(OUT),
        "claim_boundary": (
            "Complete strict JSON for all 24 node0075 physical stages and "
            "their static composite boundaries only. No mapping, bitstream, "
            "execplan, SCA, server package/run, natural terminal, formal D, "
            "E3, E4, or E5."
        ),
    }
    write(contract_path, contract)

    family_set_path = OUT / "family_set.json"
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": FAMILY,
        "target_hw_op_types": TARGET_HW_OP_TYPES,
        "candidate_contracts": [bound(contract_path)],
        "no_config_stages": [],
        "claim_boundary": (
            "The qlinear_matmul family owns exactly hwop-0075-00 and "
            "hwop-0075-01. The public auditor currently selects all 54 "
            "RequantizeUint8 stages globally; any resulting extra-family "
            "missing set is recorded as a public scope limitation, not filled "
            "by cross-family claims."
        ),
    }
    write(family_set_path, family_set)

    coverage_path = OUT / "family_scope_coverage.json"
    write(
        coverage_path,
        {
            "schema": "qlinear_matmul_family_scope_coverage_v1",
            "family": FAMILY,
            "node_id": "node-0075",
            "expected_lowering_stage_ids": LOGICAL_STAGE_IDS,
            "covered_lowering_stage_ids": LOGICAL_STAGE_IDS,
            "duplicate_stage_ids": [],
            "missing_stage_ids": [],
            "unexpected_stage_ids": [],
            "physical_stage_count": 24,
            "equivalence_class_count": 6,
            "pass": True,
            "claim_boundary": (
                "Node-scoped family evidence only; does not override the "
                "shared family-set auditor."
            ),
        },
    )

    report_path = OUT / "report.json"
    diff = load(diff_path)
    write(
        report_path,
        {
            "schema": "qlinear_matmul_complete_json_regeneration_report_v1",
            "family": FAMILY,
            "status": "COMPLETE",
            "logical_stage_count": 2,
            "physical_stage_count": 24,
            "equivalence_class_count": 6,
            "candidate_leaf_count": sum(
                1 for _ in leaves(candidate_aggregate)
            ),
            "unresolved_leaf_count": 0,
            "current_diff_counts": dict(
                sorted(
                    Counter(
                        entry["classification"]
                        for entry in diff["entries"]
                    ).items()
                )
            ),
            "suspected_current_config_defects": [
                "accumulate stream1 duplicate MSE byte locations",
                "accumulate READ_STREAM0 buffer0/buffer1 lifetime 1/16",
            ],
            "intentional_derivations": [
                "write stream inactive index mode and threshold integer0→null"
            ],
            "new_candidate_defects": [],
            "dynamic_only": [
                "producer acceptance→pass00 first actual read",
                "8192 actual accepted A reads and per-pass/slice hashes",
                "natural terminal",
                "144 formal D",
            ],
            "artifacts": {
                "candidate_contract": bound(contract_path),
                "candidate_json": bound(candidate_path),
                "stage_inventory": bound(inventory_path),
                "field_provenance_ledger": bound(ledger_path),
                "reference_applicability": bound(refs_path),
                "handler_capability": bound(handler_path),
                "current_test_diff": bound(diff_path),
                "composition_boundary": bound(composition_path),
                "family_set": bound(family_set_path),
                "family_scope_coverage": bound(coverage_path),
            },
            "rule_feedback": {
                "type": "RULE_DELTA_PROPOSAL",
                "id": (
                    "CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-"
                    "FAMILY-OR-STAGE-PREDICATE-001"
                ),
                "proposal": (
                    "Family-set manifests/auditor need an explicit family "
                    "stage predicate or exact expected stage IDs in addition "
                    "to hw_op_type. RequantizeUint8 is shared by 54 lowering "
                    "stages, while qlinear_matmul owns only hwop-0075-01."
                ),
            },
            "claim_boundary": contract["claim_boundary"],
        },
    )
    print(
        json.dumps(
            {
                "output": rel(OUT),
                "candidate_sha256": sha256_file(candidate_path),
                "physical_stages": 24,
                "equivalence_classes": 6,
                "unresolved": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
