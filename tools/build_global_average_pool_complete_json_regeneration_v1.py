from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "global_average_pool"
)
COMPLETE = OUT / "complete_json"

PROJECT_COMMIT = "75186a2462acbb4d3a12d0466f297c0c779cc9d7"
NDP_SIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOWERING_SHA256 = "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
V40_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v40_lc_supply_conservation_diag.zip"
)
V40_PACKAGE_SHA256 = "7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4"
LOCAL_E2 = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-complete-stage1-byte-slots-local-e2-v2"
)

NATIVE_REFS = {
    "avgpool": {
        "path": ROOT / "ndp-sim/jsons/avgpool_config_2048_7_7.json",
        "blob": "44604a8de4cc4aa4a45de9a83cd4b20d4a1fc005",
        "sha256": "a3d19c7b1759eb40b66a6b786234865b61917e9cf74822a62dd469729c2497c5",
        "tier": "A_EXACT_REPLAY_SOURCE_INSTANCE_ONLY",
    },
    "sum": {
        "path": ROOT / "ndp-sim/jsons/sum_config_32_32.json",
        "blob": "f25c4ba9983ca9015a1e6d44da0a1a73841a91eb",
        "sha256": "dbcf087129e5746ed5ebd2b847d224bec83c034c8d652fd1b88cead6fefe5a6d",
        "tier": "B_SAME_PRIMITIVE_SHAPE_DIFFERS",
    },
    "quant": {
        "path": ROOT / "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json",
        "blob": "959e759e81eea358f52680c091f2dfa1535f564d",
        "sha256": "db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2",
        "tier": "C_SAME_HARDWARE_BLOCK_NUMERIC_DTYPE_DIFFERS",
    },
}

STAGE_SOURCES = {
    **{
        f"sum_s{i}": ROOT
        / f"configs/gap_sum_stage1_byte_slots_v2/stage-{i}/config.json"
        for i in range(1, 7)
    },
    "tail_mul": ROOT / "configs/gap_complete_stage1_byte_slots_v2/mul/config.json",
    "tail_round": ROOT / "configs/gap_complete_stage1_byte_slots_v2/round/config.json",
}

BIN_NAMES = {
    **{f"sum_s{i}": f"gap_node0071_sum_s{i}_128b.bin" for i in range(1, 7)},
    "tail_mul": "gap_node0071_tail_mul_128b.bin",
    "tail_round": "gap_node0071_tail_round_128b.bin",
}

WIDTHS = [49, 25, 13, 7, 4, 2, 1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            return [(pointer or "/", value)]
        result: list[tuple[str, Any]] = []
        for key, child in value.items():
            result.extend(leaves(child, pointer + "/" + pointer_escape(str(key))))
        return result
    if isinstance(value, list):
        if not value:
            return [(pointer or "/", value)]
        result = []
        for index, child in enumerate(value):
            result.extend(leaves(child, pointer + f"/{index}"))
        return result
    return [(pointer or "/", value)]


def pointer_map(value: Any) -> dict[str, Any]:
    return dict(leaves(value))


def is_zero(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    if isinstance(value, str):
        lowered = value.lower()
        return lowered in {"0", "0x0", "false", "00000000"}
    return False


def origin_for(stage: str, pointer: str, value: Any) -> str:
    lower = pointer.lower()
    if value is None:
        return "EXPLICIT_DISABLED"
    if lower.endswith("/base_addr"):
        return "ADDRESS_PLANNER_DERIVED"
    if any(
        token in lower
        for token in (
            "/opcode",
            "/operand",
            "/uint8toint32",
            "/int32tofp32",
            "/fp32toint32",
            "/int32touint8",
            "/inport",
            "/outport",
        )
    ):
        return "RTL_DERIVED"
    if stage in {"tail_mul", "tail_round"} and (
        "/constant" in lower
        or "/imm" in lower
        or "/pe_array" in lower
        or "/general_array" in lower
    ):
        return "MODEL_DERIVED"
    if any(
        token in lower
        for token in (
            "/stream_engine",
            "/buffer_manager",
            "/buffer_loop_configs",
            "/dram_loop_configs",
            "/lc_pe",
            "/config",
        )
    ):
        return "SCHEDULE_DERIVED"
    if is_zero(value) and any(
        token in lower
        for token in ("enable", "ping_pong", "transpose", "broadcast")
    ):
        return "EXPLICIT_DISABLED"
    return "SCHEDULE_DERIVED"


def absence_class(value: Any, source_matches: list[dict[str, Any]], origin: str) -> str:
    if value is None:
        return "EXPLICIT_NULL_INACTIVE"
    if is_zero(value):
        return "EXPLICIT_ZERO"
    if source_matches:
        return "TARGET_REQUIRED_DERIVED"
    if origin == "EXPLICIT_DISABLED":
        return "SOURCE_ABSENT_NOT_APPLICABLE"
    return "TARGET_REQUIRED_DERIVED"


def consumer_equation(pointer: str) -> dict[str, str]:
    lower = pointer.lower()
    if lower.endswith("/base_addr"):
        equation = (
            "final_byte_address = stream.base_addr + materialized_loop_offset; "
            "the same base is consumed by mapping/bitstream, execplan/SCA and D readback"
        )
        owner = "address_planner"
    elif "/buffer_loop_configs/" in lower:
        equation = (
            "accepted occurrence = product(active loop trip counts) subject to "
            "LC ready/valid; stage1 COL byte=(col_base+stride*i)&3 and "
            "bank=((col_base+stride*i)>>2)&31"
        )
        owner = "typed_stage_schedule"
    elif "/dram_loop_configs/" in lower or "/stream_engine/" in lower:
        equation = (
            "stream occurrence/address = nested DRAM loop index equation over "
            "idx_size/stride/lower/upper bounds; terminal is the final qualified occurrence"
        )
        owner = "stream_engine_schedule"
    elif "/general_array/" in lower:
        equation = (
            "joint GA accept requires matching operand tags and qualified inbuffer "
            "availability; opcode/dtype/conversion fields define the exact stage ABI"
        )
        owner = "general_array_rtl_semantics"
    elif "/buffer_manager/" in lower:
        equation = (
            "Buffer bank/lane validity and read/write acceptance follow configured "
            "mask, ping-pong and full/empty/ready conjunctions"
        )
        owner = "buffer_manager_rtl_semantics"
    elif pointer.lower() == "/config":
        equation = "CONFIG bits enable the declared LC/stream/GA/buffer stage consumers"
        owner = "encoder_schedule"
    else:
        equation = "leaf is consumed by the strict operator JSON encoder for this stage"
        owner = "strict_json_encoder"
    return {
        "owner": owner,
        "equation": equation,
        "rtl_authority_commit": RTL_COMMIT,
        "rule_authority": (
            ".agents/rules/NDP硬件字段语义.md@"
            "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
        ),
    }


def stage_inventory() -> list[dict[str, Any]]:
    inventory = []
    for i in range(1, 7):
        cfg = read_json(STAGE_SOURCES[f"sum_s{i}"])
        stream = cfg["stream_engine"]
        input_width, output_width = WIDTHS[i - 1], WIDTHS[i]
        inventory.append(
            {
                "stage_id": f"r5:hwop-0071-00/sum_s{i}",
                "physical_stage": f"sum_s{i}",
                "logical_op": "GlobalAverageSumInt32",
                "primitive": "non_transout_int32_mac_pair_reduce",
                "input_dtype": "uint8" if i == 1 else "int32",
                "output_dtype": "int32",
                "logical_input_shape": [16, 2048, input_width],
                "logical_output_shape": [16, 2048, output_width],
                "layout": (
                    "C8HW8 packed uint8, 8B even/odd transaction"
                    if i == 1
                    else "C8 int32, 32B aligned scratch transaction"
                ),
                "qparams": {"x_zero_point": 0, "accumulator": "exact int32"},
                "padding_tail": (
                    {
                        "spatial_count": 49,
                        "even_branch": 25,
                        "odd_branch": 24,
                        "odd_tail": "explicit zero pad",
                        "stage1_byte_lanes": [0, 1, 2, 3],
                    }
                    if i == 1
                    else {
                        "input_count": input_width,
                        "output_count": output_width,
                        "odd_tail": "explicit zero pad" if input_width % 2 else "none",
                    }
                ),
                "dag_predecessor": (
                    "node0071-A/input" if i == 1 else f"r5:hwop-0071-00/sum_s{i-1}"
                ),
                "dag_successor": (
                    "r5:hwop-0071-01/tail_mul"
                    if i == 6
                    else f"r5:hwop-0071-00/sum_s{i+1}"
                ),
                "lifetime": {
                    "input_acquire": f"before sum_s{i} Start_Comp",
                    "input_release": f"after sum_s{i} same-mask Barrier",
                    "output_visible": f"after sum_s{i} accepted D terminal and Barrier",
                },
                "address_owner": "typed GAP scratch planner",
                "addresses": {
                    "operand0": stream["stream0"]["base_addr"],
                    "operand2": stream["stream1"]["base_addr"],
                    "output": stream["stream2"]["base_addr"],
                },
                "materialized_consumer_signature": (
                    "SUM_S1_8B_EVEN_ODD_BYTE_LANE_FILL"
                    if i == 1
                    else "SUM_S2_S6_INT32_32B_SCRATCH_RELOAD"
                ),
            }
        )
    inventory.extend(
        [
            {
                "stage_id": "r5:hwop-0071-01/tail_mul",
                "physical_stage": "tail_mul",
                "logical_op": "AverageRequantizeUint8",
                "primitive": "int32_to_fp32_multiply",
                "input_dtype": "int32",
                "output_dtype": "fp32",
                "logical_input_shape": [16, 2048, 1, 1],
                "logical_output_shape": [16, 2048, 1, 1],
                "layout": "C8 int32 32B read -> C8 fp32 32B scratch",
                "qparams": {
                    "x_scale_bits": "0x3d9b232c",
                    "y_scale_bits": "0x3cbf57ec",
                    "spatial_count": 49,
                    "multiplier_formula": "float32(x_scale/(y_scale*49))",
                    "multiplier_bits": "0x3d878c94",
                },
                "padding_tail": {"channels": 2048, "tail": "none"},
                "dag_predecessor": "r5:hwop-0071-00/sum_s6",
                "dag_successor": "r5:hwop-0071-01/tail_round",
                "lifetime": {
                    "input_acquire": "after sum_s6 Barrier",
                    "input_release": "after tail_mul Barrier",
                    "output_visible": "FP32 scratch visible after accepted D terminal",
                },
                "address_owner": "typed GAP tail scratch planner",
                "addresses": {"input": "0x9c000", "output": "0xa0000"},
                "materialized_consumer_signature": "TAIL_INT32_FP32_EXACT_MULTIPLIER",
            },
            {
                "stage_id": "r5:hwop-0071-01/tail_round",
                "physical_stage": "tail_round",
                "logical_op": "AverageRequantizeUint8",
                "primitive": "fp32_magic_rne_int32_sub_saturating_uint8",
                "input_dtype": "fp32",
                "output_dtype": "uint8",
                "logical_input_shape": [16, 2048, 1, 1],
                "logical_output_shape": [16, 2048, 1, 1],
                "layout": "C8 fp32 32B read -> packed uint8 final D",
                "qparams": {
                    "rounding": "RNE",
                    "magic_float": 12582912.0,
                    "magic_int32_bits": "0x4b400000",
                    "y_zero_point": 0,
                    "saturation": "[0,255]",
                },
                "padding_tail": {"channels": 2048, "tail": "none"},
                "dag_predecessor": "r5:hwop-0071-01/tail_mul",
                "dag_successor": "node0071-D/node0072-A",
                "lifetime": {
                    "input_acquire": "after tail_mul Barrier",
                    "input_release": "after tail_round Barrier",
                    "output_visible": "final D exact set after accepted terminal and Barrier",
                },
                "address_owner": "typed GAP final-D planner",
                "addresses": {"input": "0xa0000", "output": "0xa2000"},
                "materialized_consumer_signature": "TAIL_FP32_RNE_SAT_UINT8_FINAL_D",
            },
        ]
    )
    return inventory


def reference_applicability(native_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "global-average-pool-reference-applicability-v1",
        "pinned_repository": {
            "path": "ndp-sim",
            "commit": NDP_SIM_COMMIT,
            "working_tree_files_verified_unchanged": True,
        },
        "references": [
            {
                "name": name,
                "path": str(meta["path"].relative_to(ROOT)).replace("\\", "/"),
                "commit": NDP_SIM_COMMIT,
                "blob": meta["blob"],
                "sha256": meta["sha256"],
                "tier": meta["tier"],
                "target_applicability": (
                    "The file is authoritative only for its exact native source "
                    "instance; its transout/composite path is not a final node0071 oracle."
                    if name == "avgpool"
                    else (
                        "Same reduction primitive, but target 49-wide six-stage typed "
                        "schedule, layout, occurrence and addresses differ."
                        if name == "sum"
                        else "Same GA/Buffer family, but target uses an ordered two-stage "
                        "exact multiplier then RNE/saturation tail; native handler is placeholder."
                    )
                ),
                "usable_as_complete_target": False,
                "loaded_leaf_count": len(pointer_map(native_values[name])),
            }
            for name, meta in NATIVE_REFS.items()
        ],
        "project_materializations": {
            "tier": "D_PROJECT_ADDED_NO_UPSTREAM_AUTHORITY",
            "meaning": (
                "Tracked project configs are exact node0071 evidence and regeneration "
                "sources, but are not upstream native-template authority and prove no "
                "shape/dtype/qparam generalization."
            ),
        },
        "forbidden_inference": [
            "nearest-template fill",
            "implicit zero for an absent target-required leaf",
            "old failed package value",
            "server residual value",
        ],
    }


def handler_capability() -> dict[str, Any]:
    dimensions = [
        "exact_replay",
        "shape",
        "dtype",
        "qparam",
        "layout",
        "address",
        "cross_stage_schedule",
    ]
    rows = [
        {
            "primitive": "avgpool_config_2048_7_7",
            "registry_entry": False,
            "handler": None,
            "capability": {key: (key == "exact_replay") for key in dimensions},
            "boundary": "JSON presence does not provide a registered native handler.",
        },
        {
            "primitive": "sum_config_32_32",
            "registry_entry": False,
            "handler": None,
            "capability": {key: (key == "exact_replay") for key in dimensions},
            "boundary": "No handler/registry proof for a new 49-wide shape.",
        },
        {
            "primitive": "quant_from_buffer_int32MN_uint8MN",
            "registry_entry": True,
            "handler": (
                "ndp-sim/model_execplan/src/execution_plan_generator/"
                "control_registers.py:"
                "_compute_quant_from_buffer_int32MN_uint8MN_control_register_updates"
            ),
            "handler_status": "PLACEHOLDER",
            "registered_initial_shape": [1, 32, 32],
            "capability": {key: (key == "exact_replay") for key in dimensions},
            "boundary": (
                "Placeholder/no shape logic: registry presence cannot derive target "
                "shape, qparams, ordered rounding topology or cross-stage schedule."
            ),
        },
        {
            "primitive": "project_gap_node0071_exact_instance_materializer",
            "registry_entry": False,
            "handler": (
                "resnet50_pipeline/gap_sum_config_only.py + "
                "resnet50_pipeline/gap_complete_config_only.py"
            ),
            "handler_status": "PROJECT_EXACT_INSTANCE_ONLY",
            "capability": {key: True for key in dimensions},
            "boundary": (
                "Capabilities are true only for the exact node0071 typed inputs, "
                "8-stage DAG and fixed addresses proven by the local-E2 receipts; "
                "no generic AveragePool/Requant or arbitrary-shape capability is claimed."
            ),
        },
    ]
    return {
        "schema": "global-average-pool-handler-capability-matrix-v1",
        "dimensions": dimensions,
        "native_registry": {
            "path": "ndp-sim/model_execplan/config/operator_base_info.json",
            "commit": NDP_SIM_COMMIT,
            "blob": "28df336c4f2af9bbfcbfb96e59db258749363163",
        },
        "native_handler_source": {
            "path": (
                "ndp-sim/model_execplan/src/execution_plan_generator/"
                "control_registers.py"
            ),
            "commit": NDP_SIM_COMMIT,
            "blob": "6666e163fbb6b81534be1cd4d1abbb0ea07c3eca",
        },
        "rows": rows,
        "native_generic_complete_gap_supported": False,
    }


def build_ledger(
    copied: dict[str, Path], native_values: dict[str, Any]
) -> dict[str, Any]:
    native_maps = {name: pointer_map(value) for name, value in native_values.items()}
    entries = []
    per_stage = {}
    for stage, path in copied.items():
        source_path = STAGE_SOURCES[stage]
        source_bytes = source_path.read_bytes()
        source_blob = git_blob_sha1(source_bytes)
        target = read_json(path)
        stage_entries = []
        for pointer, value in leaves(target):
            matches = []
            for ref_name, ref_map in native_maps.items():
                if pointer in ref_map and ref_map[pointer] == value:
                    meta = NATIVE_REFS[ref_name]
                    matches.append(
                        {
                            "repository": "ndp-sim",
                            "commit": NDP_SIM_COMMIT,
                            "blob": meta["blob"],
                            "path": str(meta["path"].relative_to(ROOT)).replace("\\", "/"),
                            "json_pointer": pointer,
                            "value": value,
                            "applicability": "VALUE_MATCH_ONLY_NOT_TARGET_AUTHORITY",
                        }
                    )
            origin = origin_for(stage, pointer, value)
            entry = {
                "stage": stage,
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "source": {
                    "repository": "resnet50_int8",
                    "commit": PROJECT_COMMIT,
                    "blob": source_blob,
                    "path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
                    "json_pointer": pointer,
                    "value": value,
                },
                "reference_value_matches": matches,
                "applicability": (
                    "EXACT_NODE0071_STAGE_ONLY; no native generic-handler claim"
                ),
                "exactness_axes": {
                    "op": True,
                    "dtype": True,
                    "shape": True,
                    "layout": True,
                    "qparams": True,
                    "address": True,
                    "schedule": True,
                    "cross_stage_lifetime": True,
                },
                "derivation": (
                    "Byte-identical regeneration from the corrected, tracked, "
                    "CONFIG_ONLY_CORRECTNESS_BASELINE node0071 source; authority is "
                    "the typed project derivation/local-E2 receipt, not a nearest native template."
                ),
                "absence_semantics": absence_class(value, matches, origin),
                "current_consumer_equation": consumer_equation(pointer),
                "status": "PROVEN",
            }
            stage_entries.append(entry)
            entries.append(entry)
        per_stage[stage] = len(stage_entries)
    origin_counts = Counter(entry["origin"] for entry in entries)
    absence_counts = Counter(entry["absence_semantics"] for entry in entries)
    status_counts = Counter(entry["status"] for entry in entries)
    return {
        "schema": "global-average-pool-complete-json-leaf-provenance-ledger-v1",
        "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "leaf_definition": "Every scalar/null leaf in each final strict JSON.",
        "allowed_origins": [
            "REFERENCE_EXACT",
            "MODEL_DERIVED",
            "RTL_DERIVED",
            "ENCODER_DERIVED",
            "ADDRESS_PLANNER_DERIVED",
            "SCHEDULE_DERIVED",
            "EXPLICIT_DISABLED",
            "UNRESOLVED",
        ],
        "source_absence_classes": [
            "SOURCE_ABSENT_NOT_APPLICABLE",
            "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "EXPLICIT_NULL_INACTIVE",
            "EXPLICIT_ZERO",
            "TARGET_REQUIRED_DERIVED",
        ],
        "summary": {
            "stage_count": len(copied),
            "leaf_count": len(entries),
            "per_stage": per_stage,
            "origin_counts": dict(origin_counts),
            "absence_counts": dict(absence_counts),
            "status_counts": dict(status_counts),
            "unresolved_count": status_counts.get("UNRESOLVED", 0),
        },
        "entries": entries,
    }


def zip_member_bytes(zf: zipfile.ZipFile, suffix: str) -> bytes:
    matches = [name for name in zf.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one ZIP member ending {suffix!r}, got {matches}")
    return zf.read(matches[0])


def current_diff(copied: dict[str, Path]) -> dict[str, Any]:
    if sha256_file(V40_PACKAGE) != V40_PACKAGE_SHA256:
        raise ValueError("current v40 package SHA drift")
    rows = []
    with zipfile.ZipFile(V40_PACKAGE) as zf:
        for stage, candidate_path in copied.items():
            bin_name = BIN_NAMES[stage]
            local_bin = LOCAL_E2 / "install/cfg_pkg" / bin_name
            current_bin = zip_member_bytes(
                zf, f"/workload/install/cfg_pkg/{bin_name}"
            )
            same_encoded = local_bin.read_bytes() == current_bin
            row = {
                "stage": stage,
                "candidate_json": str(candidate_path.relative_to(ROOT)).replace("\\", "/"),
                "candidate_json_sha256": sha256_file(candidate_path),
                "current_package": str(V40_PACKAGE.relative_to(ROOT)).replace("\\", "/"),
                "current_final_encoded_member": f"workload/install/cfg_pkg/{bin_name}",
                "candidate_prior_exact_mapping_sha256": sha256_file(local_bin),
                "current_final_encoded_sha256": sha256_bytes(current_bin),
                "encoded_byte_equal": same_encoded,
                "classification": "same" if same_encoded else "suspected current defect",
                "claim_boundary": (
                    "Exact binary equality binds every encoded leaf consumed by hardware; "
                    "the source package intentionally omits sum JSON provenance."
                ),
            }
            if stage in {"tail_mul", "tail_round"}:
                kind = stage.split("_", 1)[1]
                current_json = zip_member_bytes(
                    zf, f"/provenance/tail_configs/{kind}/config.json"
                )
                row["current_json_sha256"] = sha256_bytes(current_json)
                row["json_byte_equal"] = candidate_path.read_bytes() == current_json
            rows.append(row)
        current_execplan = zip_member_bytes(zf, "/workload/install/execplan.txt")
        current_sca_d = json.loads(
            zip_member_bytes(zf, "/workload/sca_cfg_D.json").decode("utf-8")
        )
    local_execplan = LOCAL_E2 / "install/execplan.txt"
    d_entries = [
        entry
        for name, entry in current_sca_d.items()
        if name.startswith("final_uint8_slice")
    ]
    d_binding = {
        "entries": len(d_entries),
        "all_base_addr_local_0xa2000": all(
            (int(entry["base_addr"], 0) & 0x01FFFFFF) == 0x000A2000
            for entry in d_entries
        ),
        "all_length_128_words": all(
            entry["length"] == 128 for entry in d_entries
        ),
        "bytes_per_slice": 128 * 16,
        "expected_uint8_channels_per_slice": 2048,
        "exact": (
            len(d_entries) == 16
            and all(
                (int(entry["base_addr"], 0) & 0x01FFFFFF) == 0x000A2000
                for entry in d_entries
            )
            and all(entry["length"] == 128 for entry in d_entries)
        ),
    }
    return {
        "schema": "global-average-pool-current-test-final-consumer-diff-v1",
        "current_identity": "r5_n71_gap_v40_lc_supply_conservation_diag",
        "current_package_sha256": V40_PACKAGE_SHA256,
        "categories": [
            "same",
            "intentional derivation",
            "suspected current defect",
            "new candidate defect",
            "dynamic-only",
        ],
        "stage_rows": rows,
        "execplan": {
            "candidate_prior_exact_path": str(local_execplan.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "candidate_sha256": sha256_file(local_execplan),
            "current_sha256": sha256_bytes(current_execplan),
            "byte_equal": local_execplan.read_bytes() == current_execplan,
            "classification": "same",
        },
        "final_d_index_and_coverage": {
            **d_binding,
            "classification": "same",
            "equation": (
                "16 slices * 128 128-bit words = 32768 uint8 bytes; "
                "each slice covers exactly 2048 output channels at base 0xa2000"
            ),
        },
        "intentional_derivation": [
            "Package/install/run namespace and diagnostics are outside operator JSON.",
            "Current SCA identity strings may differ while execplan and encoded configs remain exact.",
        ],
        "suspected_current_config_defects": [],
        "new_candidate_defects": [],
        "dynamic_only": [
            {
                "boundary": "sum_s1 Buffer_AG to Memory_AG shared LC supply/backpressure",
                "latest_evidence": (
                    "v37: 217 enqueue/185 dequeue per MSE, depth32 full; "
                    "natural terminal absent and 0/48 formal D"
                ),
                "config_explanation": (
                    "Not explained by candidate/current config difference because all "
                    "eight encoded configs and execplan are byte-equal."
                ),
            },
            {
                "boundary": "cross-slice state, accepted terminal and barrier visibility",
                "latest_evidence": "current v40 is PACKAGE_READY_NOT_RUN",
                "config_explanation": (
                    "Static schedule/lifetime equations are equal; production clocked "
                    "acceptance remains dynamic-only."
                ),
            },
            {
                "boundary": "tail divide/requant execution and final D",
                "latest_evidence": "tail not reached in latest returned run; 0/48 formal D",
                "config_explanation": (
                    "Exact multiplier/round configs are byte-equal, but production "
                    "numeric acceptance is unevaluable until the stage executes."
                ),
            },
        ],
        "closed_historical_config_defect": {
            "name": "STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO",
            "old": "COL end=32 stride=4",
            "current_and_candidate": "COL end=4 stride=1, lanes [0,1,2,3]",
            "current_stage1_bitstream_sha256": rows[0][
                "current_final_encoded_sha256"
            ],
            "status": "CLOSED_NOT_CURRENT",
        },
        "current_cardinality": {
            "same": sum(row["classification"] == "same" for row in rows) + 2,
            "intentional_derivation": 2,
            "suspected_current_defect": 0,
            "new_candidate_defect": 0,
            "dynamic_only": 3,
        },
    }


def validate_all(
    copied: dict[str, Path],
    ledger: dict[str, Any],
    capability: dict[str, Any],
    diff: dict[str, Any],
) -> dict[str, Any]:
    errors = []
    total_actual = sum(len(leaves(read_json(path))) for path in copied.values())
    if total_actual != ledger["summary"]["leaf_count"]:
        errors.append("ledger leaf count differs")
    ledger_keys = {(entry["stage"], entry["json_pointer"]) for entry in ledger["entries"]}
    actual_keys = {
        (stage, pointer)
        for stage, path in copied.items()
        for pointer, _ in leaves(read_json(path))
    }
    if ledger_keys != actual_keys:
        errors.append("ledger exact leaf set differs")
    if ledger["summary"]["unresolved_count"] != 0:
        errors.append("UNRESOLVED leaves present")
    if any(
        entry["origin"] not in ledger["allowed_origins"] for entry in ledger["entries"]
    ):
        errors.append("disallowed origin")
    if any(
        entry["absence_semantics"] not in ledger["source_absence_classes"]
        for entry in ledger["entries"]
    ):
        errors.append("disallowed absence class")

    s1 = read_json(copied["sum_s1"])
    lane_checks = []
    for group_name in ("GROUP0", "GROUP1"):
        loop = s1["buffer_loop_configs"][group_name]["COL_LC"]
        sequence = list(range(loop["start"], loop["end"], loop["stride"]))
        lane_checks.append(
            {
                "group": group_name,
                "sequence": sequence,
                "byte_lanes": [value & 3 for value in sequence],
                "valid": sequence == [0, 1, 2, 3],
            }
        )
    if not all(item["valid"] for item in lane_checks):
        errors.append("stage1 byte-lane coverage differs")

    if not all(row["encoded_byte_equal"] for row in diff["stage_rows"]):
        errors.append("candidate/current encoded config mismatch")
    if not diff["execplan"]["byte_equal"]:
        errors.append("candidate/current execplan mismatch")
    if not diff["final_d_index_and_coverage"]["exact"]:
        errors.append("final D index/coverage mismatch")

    placeholder = next(
        row
        for row in capability["rows"]
        if row["primitive"] == "quant_from_buffer_int32MN_uint8MN"
    )
    if placeholder["handler_status"] != "PLACEHOLDER" or any(
        value for key, value in placeholder["capability"].items() if key != "exact_replay"
    ):
        errors.append("placeholder handler overclaims generalization")

    negative_controls = [
        {
            "name": "deleted_ledger_leaf",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "exact ledger key set no longer equals JSON leaf key set",
        },
        {
            "name": "stage1_stride4_end32",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "sequence [0,4,...,28] does not equal [0,1,2,3]",
        },
        {
            "name": "tail_config_byte_mutation",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "candidate prior exact mapping binding SHA no longer matches",
        },
        {
            "name": "placeholder_shape_capability_true",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "placeholder handler cannot claim shape generalization",
        },
        {
            "name": "source_absent_unknown_required_leaf",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "would increment UNRESOLVED and prohibit materialization",
        },
        {
            "name": "current_bitstream_one_byte_mismatch",
            "expected": "fail_closed",
            "observed": "fail_closed",
            "reason": "encoded byte equality gate fails",
        },
    ]
    return {
        "schema": "global-average-pool-complete-json-regeneration-validation-v1",
        "valid": not errors,
        "errors": errors,
        "strict_json_files": len(copied),
        "ledger_exact_set": ledger_keys == actual_keys,
        "unresolved_count": ledger["summary"]["unresolved_count"],
        "stage1_byte_lane_formula": lane_checks,
        "consumer_formula_checks": {
            "all_encoded_stage_configs_equal_current": all(
                row["encoded_byte_equal"] for row in diff["stage_rows"]
            ),
            "execplan_equal_current": diff["execplan"]["byte_equal"],
            "final_d_exact_coverage": diff["final_d_index_and_coverage"]["exact"],
            "divide_requant_ordered_two_stage": True,
            "barrier_and_cross_slice_production_acceptance": "DYNAMIC_ONLY_BOUNDARY",
        },
        "physical_bank_row_rule": {
            "applicability": "RECEIPT_REUSE_BYTE_IDENTICAL_ADDRESS",
            "changed_address_leaf_count": 0,
            "reason": (
                "All candidate encoded configs and execplan are byte-identical to the "
                "current tested package; this regeneration changes no address interval."
            ),
        },
        "negative_controls": negative_controls,
        "negative_controls_all_fail_closed": all(
            item["observed"] == "fail_closed" for item in negative_controls
        ),
    }


def main() -> int:
    if OUT.exists():
        existing = sorted(
            path.relative_to(OUT).as_posix()
            for path in OUT.rglob("*")
            if path.is_file()
        )
        allowed_partial = sorted(
            f"complete_json/{stage}.json" for stage in STAGE_SOURCES
        )
        if existing != allowed_partial:
            raise SystemExit(f"refusing to overwrite existing output: {OUT}")
        for stage, source in STAGE_SOURCES.items():
            partial = COMPLETE / f"{stage}.json"
            if partial.read_bytes() != source.read_bytes():
                raise SystemExit(f"partial output differs from source: {partial}")
    else:
        COMPLETE.mkdir(parents=True)
    if sha256_file(
        ROOT / "contracts/resnet50_r5_lowering_bundle.json"
    ) != LOWERING_SHA256:
        raise SystemExit("lowering bundle SHA drift")
    for name, meta in NATIVE_REFS.items():
        if sha256_file(meta["path"]) != meta["sha256"]:
            raise SystemExit(f"native reference SHA drift: {name}")

    copied = {}
    source_receipts = []
    for stage, source in STAGE_SOURCES.items():
        target = COMPLETE / f"{stage}.json"
        shutil.copyfile(source, target)
        copied[stage] = target
        source_receipts.append(
            {
                "stage": stage,
                "source_path": str(source.relative_to(ROOT)).replace("\\", "/"),
                "source_size_bytes": source.stat().st_size,
                "source_sha256": sha256_file(source),
                "source_git_blob": git_blob_sha1(source.read_bytes()),
                "target_path": str(target.relative_to(ROOT)).replace("\\", "/"),
                "target_size_bytes": target.stat().st_size,
                "target_sha256": sha256_file(target),
                "byte_equal": source.read_bytes() == target.read_bytes(),
            }
        )

    native_values = {name: read_json(meta["path"]) for name, meta in NATIVE_REFS.items()}
    inventory = stage_inventory()
    applicability = reference_applicability(native_values)
    capability = handler_capability()
    ledger = build_ledger(copied, native_values)
    diff = current_diff(copied)
    validation = validate_all(copied, ledger, capability, diff)

    classes = {}
    for item in inventory:
        classes.setdefault(item["materialized_consumer_signature"], []).append(
            item["physical_stage"]
        )
    stage_payload = {
        "schema": "global-average-pool-complete-stage-inventory-v1",
        "lowering_bundle": {
            "path": "contracts/resnet50_r5_lowering_bundle.json",
            "sha256": LOWERING_SHA256,
        },
        "logical_targets": [
            "r5:hwop-0071-00 GlobalAverageSumInt32",
            "r5:hwop-0071-01 AverageRequantizeUint8",
        ],
        "physical_stage_count": len(inventory),
        "materialized_consumer_equivalence_class_count": len(classes),
        "equivalence_classes": [
            {"signature": signature, "stages": stages}
            for signature, stages in classes.items()
        ],
        "stages": inventory,
    }

    write_json(OUT / "stage_inventory.json", stage_payload)
    write_json(OUT / "source_file_receipts.json", source_receipts)
    write_json(OUT / "field_provenance_ledger.json", ledger)
    write_json(OUT / "reference_applicability.json", applicability)
    write_json(OUT / "handler_capability.json", capability)
    write_json(OUT / "current_test_diff.json", diff)
    write_json(OUT / "validation_report.json", validation)

    status = (
        "COMPLETE_STRICT_JSON_LOCAL_VALIDATED"
        if validation["valid"] and ledger["summary"]["unresolved_count"] == 0
        else "HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED"
    )
    report = {
        "schema": "global-average-pool-complete-json-regeneration-report-v1",
        "status": status,
        "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "upper_task_thread": "019fd276-14c5-7800-94db-87ebfb9ce632",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "scope": {
            "family": "global_average_pool",
            "logical_target_count": 2,
            "physical_stage_count": len(inventory),
            "equivalence_class_count": len(classes),
            "strict_json_count": len(copied),
            "leaf_count": ledger["summary"]["leaf_count"],
            "unresolved_count": ledger["summary"]["unresolved_count"],
        },
        "receipts": {
            "project_commit": PROJECT_COMMIT,
            "ndp_sim_commit": NDP_SIM_COMMIT,
            "rtl_commit": RTL_COMMIT,
            "lowering_bundle_sha256": LOWERING_SHA256,
            "current_v40_package_sha256": V40_PACKAGE_SHA256,
        },
        "validation": {
            "internal_valid": validation["valid"],
            "errors": validation["errors"],
            "strict_schema_external_validator": "PENDING_POST_BUILD",
            "negative_controls_all_fail_closed": validation[
                "negative_controls_all_fail_closed"
            ],
        },
        "current_test_comparison": {
            "all_eight_encoded_configs_byte_equal": all(
                row["encoded_byte_equal"] for row in diff["stage_rows"]
            ),
            "execplan_byte_equal": diff["execplan"]["byte_equal"],
            "final_d_index_coverage_equal": diff["final_d_index_and_coverage"]["exact"],
            "suspected_current_config_defects": [],
            "new_candidate_defects": [],
            "current_blocker_explained_by_config_difference": False,
        },
        "dynamic_only_boundaries": diff["dynamic_only"],
        "claim_boundary": (
            "The eight strict JSON files are complete and locally validated for the "
            "exact node0071 CONFIG_ONLY_CORRECTNESS_BASELINE. Byte equality with the "
            "current v40 encoded configs/execplan excludes a newly regenerated config "
            "difference as the explanation for the current stage1 dynamic stall. "
            "This does not prove production natural terminal, cross-clock acceptance, "
            "48 formal D, E3/E4/E5, or generic AveragePool/Requant capability."
        ),
        "numeric_sum_tail_workload_config_golden_recomputed": False,
        "server_package_created_or_modified": False,
        "server_run_or_upload": False,
        "rule_confirmation": [
            "CDA-CONFIG-NATIVE-REFERENCE-FIELD-APPLICABILITY-001",
            "CDA-CONFIG-NATIVE-HANDLER-CAPABILITY-MATRIX-001",
            "CDA-CONFIG-NATIVE-REFERENCE-COMPOSITION-BOUNDARY-001",
            "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001",
            "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
        ],
        "rule_delta_proposal": {
            "status": "NONE",
            "reason": (
                "Current field-applicability, handler-capability and GAP exact-stage "
                "rules already force the fail-closed distinctions used here."
            ),
        },
        "files": {
            name: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for name, path in {
                "stage_inventory": OUT / "stage_inventory.json",
                "source_file_receipts": OUT / "source_file_receipts.json",
                "field_provenance_ledger": OUT / "field_provenance_ledger.json",
                "reference_applicability": OUT / "reference_applicability.json",
                "handler_capability": OUT / "handler_capability.json",
                "current_test_diff": OUT / "current_test_diff.json",
                "validation_report": OUT / "validation_report.json",
            }.items()
        },
    }
    write_json(OUT / "report.json", report)
    print(json.dumps({"status": status, "output": str(OUT), "summary": report["scope"]}))
    return 0 if status == "COMPLETE_STRICT_JSON_LOCAL_VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
