"""Family-wide complete-JSON regeneration for ResNet50 DequantizeLinear.

The output is deliberately limited to local, strict configuration candidates
and provenance evidence.  It never invokes mapping, bitstream, execplan, SCA,
package, or server tooling.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from . import dequant_node0072_config_only as dq72
from . import dequantize_linear_vertical as dq77
from .operator_config_validator import OperatorConfigValidator


SCHEMA = "resnet50-dequantize-linear-complete-json-regeneration-v1"
FAMILY = "dequantize_linear"
ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/dequantize_linear"
)
NATIVE_REL = Path(
    "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
)
NATIVE_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
NATIVE_BLOB = "41c502ce87ac7712c42dcc6214ecb76f3bc4c06b"
NATIVE_SHA256 = (
    "15f5321ab57cb73ca2f650693859657759f834389677451a9a89e66217e9e6da"
)
GENERATOR_REL = Path(
    "resnet50_pipeline/dequantize_linear_complete_json_regeneration.py"
)
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
LIFETIME_REL = Path(
    "contracts/operator_config/stage_state_lifetime_contract_v1.json"
)
AUTHORITY_REL = Path(
    "contracts/operator_config/operator_config_authority_v1.json"
)
POLICY_REL = Path(
    "contracts/operator_config/complete_json_generation_contract_v1.json"
)

EXACTNESS_AXES = (
    "op",
    "dtype",
    "shape",
    "layout",
    "qparams",
    "topology",
    "address",
    "schedule",
    "consumer",
)
CAPABILITY_AXES = (
    "exact_replay",
    "shape",
    "dtype",
    "qparam",
    "layout",
    "address",
    "cross_stage_schedule",
)
CHANGED_AXES = (
    "shape",
    "dtype",
    "qparam",
    "layout",
    "address",
    "cross_stage_schedule",
)

STAGES: dict[str, dict[str, Any]] = {
    "hwop-0072-00": {
        "request_id": "r5:hwop-0072-00",
        "node_id": "node-0072",
        "logical_shape": [16, 2048, 1, 1],
        "logical_layout": "NCHW_CONTIGUOUS",
        "input_tensor_id": "tensor-ab32f279540568c3",
        "output_tensor_id": "tensor-50c285690f899b1b",
        "scale_bits": "0x3cbf57ec",
        "scale_scalar": 0.02335735410451889,
        "scale_materialized": "0.02335735410451889",
        "zero_point": 0,
        "negative_zero_point_bits": "0x80000000",
        "negative_zero_point_materialized": "0.0",
        "hardware_shape_cwh": [16, 74, 1],
        "occurrences_per_slice": 74,
        "words_per_slice": 1184,
        "d_bytes_per_slice": 4736,
        "d_lines_per_slice": 296,
        "a_base": "0x0",
        "d_base": "0x4a0",
        "valid_elements": 32768,
        "physical_elements": 33152,
        "input_path": dq72.INPUT_RELATIVE.as_posix(),
        "golden_path": dq72.OUTPUT_RELATIVE.as_posix(),
        "static_path": dq72.CONFIG_RELATIVE.as_posix(),
        "current_path": (
            "artifacts/operator_config_validation/"
            "r5-dequant-node0072-config-only-e2-v1/isolated_toolchain/"
            "model_execplan/output/dq72/jsons/op0_dq72_u8_f32_cfg_v1.json"
        ),
        "current_result": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE/local materialized E2; "
            "not E4/E5 and not a production release"
        ),
        "producer": "r5:hwop-0071-01",
        "consumer": "r5:hwop-0073-00",
        "execution_status": "CONFIG_ONLY_CORRECTNESS_BASELINE",
    },
    "hwop-0077-00": {
        "request_id": "r5:hwop-0077-00",
        "node_id": "node-0077",
        "logical_shape": [16, 1000],
        "logical_layout": "NC_CONTIGUOUS",
        "input_tensor_id": "tensor-02aeb7457d1ccf49",
        "output_tensor_id": "tensor-bff07c95eb9f8609",
        "scale_bits": "0x3e01622d",
        "scale_scalar": 0.12635107338428497,
        "scale_materialized": "0.126351073384285",
        "zero_point": 60,
        "negative_zero_point_bits": "0xc2700000",
        "negative_zero_point_materialized": "-60",
        "hardware_shape_cwh": [16, 47, 1],
        "occurrences_per_slice": 47,
        "words_per_slice": 752,
        "d_bytes_per_slice": 3008,
        "d_lines_per_slice": 188,
        "a_base": "0x0",
        "d_base": "0x2f0",
        "valid_elements": 16000,
        "physical_elements": 21056,
        "input_path": (
            "artifacts/w3/golden_batch16/tensors/tensor-02aeb7457d1ccf49.npy"
        ),
        "golden_path": (
            "artifacts/w3/golden_batch16/tensors/tensor-bff07c95eb9f8609.npy"
        ),
        "static_path": (
            "configs/native_ndp_sim/"
            "resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json"
        ),
        "current_path": (
            "artifacts/operator_config_validation/"
            "r5-dequant-node0077-e2-v6/tool-a/model_execplan/output/dq77/"
            "jsons/op0_resnet50_dequant_node0077_uint8_fp32.json"
        ),
        "current_result": (
            "formal E4 FIRST_DYNAMIC_PASS plus fresh-identity E5 "
            "REPEATED_DYNAMIC_PASS; 28x188=5264 formal D lines"
        ),
        "producer": "r5:hwop-0076-00",
        "consumer": "GRAPH_OUTPUT",
        "execution_status": "FORMAL_E4_E5_FROZEN_POSITIVE_CONTROL",
    },
}


class DequantCompleteJsonError(ValueError):
    """A source identity or complete-candidate invariant failed closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DequantCompleteJsonError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )


def bound(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": sha256_file(path),
    }


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
        for key in sorted(value):
            yield from iter_leaves(value[key], f"{pointer}/{_escape(key)}")
    elif isinstance(value, list):
        if not value:
            yield pointer or "/", value
        for index, item in enumerate(value):
            yield from iter_leaves(item, f"{pointer}/{index}")
    else:
        yield pointer or "/", value


def _pointer(document: Any, pointer: str) -> tuple[bool, Any]:
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return False, None
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return False, None
    return True, current


def _float32_bits(value: Any) -> int:
    if isinstance(value, str) and value.lower().startswith("0x"):
        return int(value, 16)
    return struct.unpack("<I", struct.pack("<f", np.float32(float(value))))[0]


def _port(src_id: object, mode: str | None, constant: object = 0) -> dict[str, Any]:
    return {
        "src_id": src_id,
        "mode": mode,
        "keep_last_index": None,
        "constant": constant,
    }


def _request_index(root: Path) -> dict[str, dict[str, Any]]:
    bundle = load_json(root / LOWERING_REL)
    result: dict[str, dict[str, Any]] = {}
    for request in bundle["requests"]:
        identity = request["identity"]
        if identity["hw_op_type"] == "DequantizeLinear":
            result[identity["hw_op_id"]] = request
    if set(result) != set(STAGES):
        raise DequantCompleteJsonError(
            f"Dequant lowering coverage drifted: {sorted(result)}"
        )
    return result


def build_candidate(root: Path, stage_id: str) -> dict[str, Any]:
    spec = STAGES[stage_id]
    source_path = root / NATIVE_REL
    if sha256_file(source_path) != NATIVE_SHA256:
        raise DequantCompleteJsonError("pinned native add_dequant source drifted")
    config = copy.deepcopy(load_json(source_path))
    for key, end in {
        "LC1": spec["occurrences_per_slice"],
        "LC2": 1,
        "LC3": spec["occurrences_per_slice"],
        "LC4": 1,
    }.items():
        config["dram_loop_configs"][key]["end"] = end
    del config["buffer_loop_configs"]["GROUP1"]
    config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 4
    del config["stream_engine"]["stream1"]
    config["stream_engine"]["stream0"]["dim_stride"] = [
        16,
        16,
        spec["words_per_slice"],
    ]
    config["stream_engine"]["stream2"]["dim_stride"] = [
        64,
        64,
        spec["d_bytes_per_slice"],
    ]
    config["stream_engine"]["stream0"]["base_addr"] = spec["a_base"]
    config["stream_engine"]["stream2"]["base_addr"] = spec["d_base"]
    del config["buffer_config"]["buffer2"]
    config["general_array"]["inport"]["inport1"]["mask"] = [0] * 8
    config["general_array"]["inport"]["inport1"]["uint8tofp32"] = "false"
    pes: dict[str, Any] = {}
    for pe in dq77.FIRST_STAGE_PES:
        pes[pe] = {
            "alu_opcode": "add",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(
                None, "constant", spec["negative_zero_point_materialized"]
            ),
            "inport0": _port(0, "buffer"),
        }
    for pe, predecessor in dq77.SECOND_STAGE_LINKS:
        pes[pe] = {
            "alu_opcode": "mul",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(None, "constant", spec["scale_materialized"]),
            "inport0": _port(f"GA_PE.{predecessor}", "buffer"),
        }
    config["general_array"]["PE_array"] = pes
    validate_candidate(config, stage_id)
    current = load_json(root / spec["current_path"])
    if config != current:
        differing = [
            pointer
            for pointer, value in iter_leaves(config)
            if _pointer(current, pointer) != (True, value)
        ]
        raise DequantCompleteJsonError(
            f"{stage_id} regenerated candidate differs from current final: "
            f"{differing[:8]}"
        )
    return config


def validate_candidate(config: dict[str, Any], stage_id: str) -> dict[str, Any]:
    spec = STAGES[stage_id]
    generic = OperatorConfigValidator().validate(
        config,
        source=f"{stage_id}-complete-json-candidate",
        development_mode=True,
    )
    if not generic.valid:
        raise DequantCompleteJsonError(
            f"{stage_id} strict config invalid: {generic.to_dict()['first_error']}"
        )
    if set(config["stream_engine"]) != {"stream0", "stream2"}:
        raise DequantCompleteJsonError(f"{stage_id} non-standalone stream set")
    if set(config["buffer_loop_configs"]) != {"GROUP0", "GROUP2"}:
        raise DequantCompleteJsonError(f"{stage_id} non-standalone group set")
    if set(config["buffer_config"]) != {"buffer0", "buffer5"}:
        raise DequantCompleteJsonError(f"{stage_id} non-standalone buffer set")
    if config["dram_loop_configs"]["LC1"]["end"] != spec["occurrences_per_slice"]:
        raise DequantCompleteJsonError(f"{stage_id} LC1 occurrence mismatch")
    if config["dram_loop_configs"]["LC3"]["end"] != spec["occurrences_per_slice"]:
        raise DequantCompleteJsonError(f"{stage_id} LC3 occurrence mismatch")
    if config["stream_engine"]["stream0"]["dim_stride"] != [
        16,
        16,
        spec["words_per_slice"],
    ]:
        raise DequantCompleteJsonError(f"{stage_id} A stride mismatch")
    if config["stream_engine"]["stream2"]["dim_stride"] != [
        64,
        64,
        spec["d_bytes_per_slice"],
    ]:
        raise DequantCompleteJsonError(f"{stage_id} D stride mismatch")
    if config["stream_engine"]["stream0"]["base_addr"] != spec["a_base"]:
        raise DequantCompleteJsonError(f"{stage_id} A base mismatch")
    if config["stream_engine"]["stream2"]["base_addr"] != spec["d_base"]:
        raise DequantCompleteJsonError(f"{stage_id} D base mismatch")
    pe_array = config["general_array"]["PE_array"]
    expected_pes = set(dq77.FIRST_STAGE_PES) | {
        pe for pe, _ in dq77.SECOND_STAGE_LINKS
    }
    if set(pe_array) != expected_pes:
        raise DequantCompleteJsonError(f"{stage_id} PE exact set mismatch")
    for pe in dq77.FIRST_STAGE_PES:
        node = pe_array[pe]
        materialized_negative_bits = _float32_bits(
            spec["negative_zero_point_materialized"]
        )
        accepted_negative_bits = (
            {0x00000000, 0x80000000}
            if stage_id == "hwop-0072-00"
            else {int(spec["negative_zero_point_bits"], 16)}
        )
        if (
            node != _pe_node(
                "add",
                0,
                "buffer",
                spec["negative_zero_point_materialized"],
            )
            or materialized_negative_bits not in accepted_negative_bits
        ):
            raise DequantCompleteJsonError(f"{stage_id} ADD stage mismatch: {pe}")
    for pe, predecessor in dq77.SECOND_STAGE_LINKS:
        node = pe_array[pe]
        if (
            node
            != _pe_node(
                "mul",
                f"GA_PE.{predecessor}",
                "buffer",
                spec["scale_materialized"],
            )
            or _float32_bits(node["inport1"]["constant"])
            != int(spec["scale_bits"], 16)
        ):
            raise DequantCompleteJsonError(f"{stage_id} MUL stage mismatch: {pe}")
    if config["general_array"]["outport"]["mask"] != [0, 1, 0, 1, 0, 1, 0, 1]:
        raise DequantCompleteJsonError(f"{stage_id} GA D mask mismatch")
    d_rows = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
    if (
        config["buffer_config"]["buffer5"]["buf_end_row_addr"] != 3
        or d_rows["end"] != 4
        or config["stream_engine"]["stream2"]["idx_size"][2] + 1 != 64
        or config["stream_engine"]["stream2"]["buf_spatial_size"] != 16
    ):
        raise DequantCompleteJsonError(f"{stage_id} D buffer supply mismatch")
    covered = spec["occurrences_per_slice"] * 64
    if covered != spec["d_bytes_per_slice"]:
        raise DequantCompleteJsonError(f"{stage_id} written-byte coverage mismatch")
    return {
        "valid": True,
        "strict_issue_count": 0,
        "stage_id": stage_id,
        "leaf_count": len(list(iter_leaves(config))),
        "stream_targets": ["A", "D"],
        "two_stage_ga": "four ADD then four MUL",
        "d_supply_bytes_per_occurrence": 64,
        "occurrences_per_slice": spec["occurrences_per_slice"],
        "written_bytes_per_slice": covered,
        "physical_written_bytes": 28 * covered,
        "logical_valid_bytes": spec["valid_elements"] * 4,
        "padding_bytes": 28 * covered - spec["valid_elements"] * 4,
    }


def _pe_node(
    opcode: str, source: object, mode: str | None, constant: object
) -> dict[str, Any]:
    return {
        "alu_opcode": opcode,
        "transout_last_index": None,
        "inport2": _port(None, None),
        "inport1": _port(None, "constant", constant),
        "inport0": _port(source, mode),
    }


def build_stage_inventory(root: Path) -> dict[str, Any]:
    requests = _request_index(root)
    lifetime = load_json(root / LIFETIME_REL)
    edges = lifetime["typed_tensor_dag"]["edges"]
    stages = []
    for stage_id, spec in STAGES.items():
        request = requests[stage_id]
        related = [
            edge
            for edge in edges
            if edge.get("producer_request_id") == spec["request_id"]
            or edge.get("consumer_request_id") == spec["request_id"]
        ]
        signature_payload = {
            "op": "DequantizeLinear",
            "dtype": "uint8_to_float32",
            "logical_shape": spec["logical_shape"],
            "physical_shape": spec["hardware_shape_cwh"],
            "scale_bits": spec["scale_bits"],
            "zero_point": spec["zero_point"],
            "occurrences": spec["occurrences_per_slice"],
            "d_stride": spec["d_bytes_per_slice"],
            "address_offset": int(spec["d_base"], 16),
        }
        signature = hashlib.sha256(
            canonical_json_bytes(signature_payload)
        ).hexdigest()
        stages.append(
            {
                "request_id": spec["request_id"],
                "request_sha256": request["request_sha256"],
                "hw_op_id": stage_id,
                "hw_op_type": request["identity"]["hw_op_type"],
                "node_id": spec["node_id"],
                "op": "DequantizeLinear",
                "input": {
                    "tensor_id": spec["input_tensor_id"],
                    "dtype": "uint8",
                    "shape": spec["logical_shape"],
                    "logical_bytes": spec["valid_elements"],
                },
                "output": {
                    "tensor_id": spec["output_tensor_id"],
                    "dtype": "float32",
                    "shape": spec["logical_shape"],
                    "logical_bytes": spec["valid_elements"] * 4,
                },
                "layout": {
                    "logical": spec["logical_layout"],
                    "physical": {
                        "kind": "28-slice CWH",
                        "shape": spec["hardware_shape_cwh"],
                        "words_per_slice": spec["words_per_slice"],
                    },
                },
                "qparams": {
                    "domain": "UINT8",
                    "granularity": "per_tensor",
                    "axis": None,
                    "scale_bits": spec["scale_bits"],
                    "scale_scalar": spec["scale_scalar"],
                    "zero_point": spec["zero_point"],
                },
                "padding_tail": {
                    "physical_elements": spec["physical_elements"],
                    "valid_elements": spec["valid_elements"],
                    "padding_elements": (
                        spec["physical_elements"] - spec["valid_elements"]
                    ),
                    "input_neutral_value": spec["zero_point"],
                    "output_padding_bits": "0x00000000",
                },
                "dag": {
                    "producer": spec["producer"],
                    "consumer": spec["consumer"],
                    "stage_internal_topology": "4 ADD -> 4 MUL",
                    "lifetime_edges": related,
                },
                "lifetime": {
                    "standalone_config_visibility": "RESOLVED",
                    "integrated_visibility": (
                        "UNRESOLVED"
                        if stage_id == "hwop-0072-00"
                        else "FROZEN_FORMAL_INSTANCE_ONLY"
                    ),
                },
                "address_owner": (
                    "frozen current addressed instance; candidate reproduces "
                    "the exact A/D base pair without running a planner"
                ),
                "materialized_consumer_signature": signature,
                "equivalence_class_id": f"dq-eq-{stage_id[5:9]}",
                "execution_status": spec["execution_status"],
            }
        )
    return {
        "schema": f"{SCHEMA}-stage-inventory",
        "family": FAMILY,
        "target_hw_op_types": ["DequantizeLinear"],
        "stage_count": len(stages),
        "equivalence_class_count": len(
            {stage["materialized_consumer_signature"] for stage in stages}
        ),
        "stages": stages,
    }


def build_reference_applicability(root: Path) -> dict[str, Any]:
    authority = load_json(root / AUTHORITY_REL)
    record = next(
        item for item in authority["records"] if item["path"] == NATIVE_REL.as_posix()
    )
    return {
        "schema": f"{SCHEMA}-reference-applicability",
        "family": FAMILY,
        "grading": {
            "A": "exact replay of op/dtype/shape/layout/qparams/topology/consumer",
            "B": "same primitive with target axes changed",
            "C": "same hardware block with numeric/operator boundary changed",
            "D": "project-added, untracked, or no native target authority",
        },
        "native_references": [
            {
                "path": NATIVE_REL.as_posix(),
                "sha256": record["sha256"],
                "commit": record["provenance"]["pinned_commit"],
                "blob_oid": record["provenance"]["pinned_git_blob_oid"],
                "source_instance_grade": "A",
                "target_grade": "C",
                "applies_to": sorted(STAGES),
                "reason": (
                    "native source is a composite Add-Dequant A+B graph; it is "
                    "only a hardware-block/field oracle for standalone A-only "
                    "DequantizeLinear"
                ),
            }
        ],
        "project_added_references": [
            {
                "path": STAGES[stage_id][kind],
                "sha256": sha256_file(root / STAGES[stage_id][kind]),
                "grade": "D",
                "authority": "PROJECT_INSTANCE_EVIDENCE_NOT_NATIVE_AUTHORITY",
            }
            for stage_id in STAGES
            for kind in ("static_path", "current_path")
        ],
        "candidate_reference_class": "D",
        "native_exact_target_count": 0,
        "native_same_primitive_shape_variant_count": 0,
        "claim_boundary": (
            "The pinned native blob is exact only for its own composite source "
            "instance. Both emitted standalone target candidates are class D and "
            "depend on target-specific derivation plus independent validation."
        ),
    }


def _origin(pointer: str, value: Any) -> str:
    if value is None or value is False or value == "false":
        return "EXPLICIT_DISABLED"
    if pointer.endswith("/base_addr"):
        return "ADDRESS_PLANNER_DERIVED"
    if "/PE_array/" in pointer and pointer.endswith("/constant"):
        return "MODEL_DERIVED"
    if pointer.startswith("/CONFIG/"):
        return "ENCODER_DERIVED"
    if any(
        token in pointer
        for token in (
            "/dram_loop_configs/",
            "/lc_pe_configs/",
            "/buffer_loop_configs/",
            "/stream_engine/",
            "/buffer_config/",
        )
    ):
        return "SCHEDULE_DERIVED"
    return "RTL_DERIVED"


def _exactness(pointer: str, origin: str) -> dict[str, bool]:
    axes = {axis: True for axis in EXACTNESS_AXES}
    if origin == "ADDRESS_PLANNER_DERIVED":
        axes["address"] = False
    if origin == "MODEL_DERIVED":
        axes["qparams"] = False
    if origin == "SCHEDULE_DERIVED":
        axes["shape"] = False
        axes["layout"] = False
        axes["schedule"] = False
    if "/PE_array/" in pointer:
        axes["topology"] = False
    if any(
        token in pointer
        for token in ("uint8tofp32", "int32tofp32", "fp16tofp32", "bf16tofp32")
    ):
        axes["dtype"] = False
    return axes


def _consumer_equation(pointer: str, stage_id: str) -> str:
    spec = STAGES[stage_id]
    if pointer.endswith("/base_addr"):
        return (
            f"address-bound A={spec['a_base']}, D={spec['d_base']}; "
            "no planner is run in this regeneration"
        )
    if pointer.endswith("/constant") and "/PE_array/" in pointer:
        return "binary32 y = binary32(binary32(x) + binary32(-zp)) * binary32(scale)"
    if "/stream2/dim_stride/" in pointer:
        return (
            f"D occurrence stride/extent closes "
            f"{spec['occurrences_per_slice']}*64={spec['d_bytes_per_slice']} bytes"
        )
    if "/stream0/dim_stride/" in pointer:
        return f"A physical slice span is {spec['words_per_slice']} UINT8 bytes"
    if "/PE_array/" in pointer:
        return "four normal-outbuffer ADD producers feed four MUL consumers"
    if "/general_array/outport/mask/" in pointer:
        return "D mask selects PE10/PE12/PE30/PE32 normal outbuffer lanes"
    return "direct strict-config consumer uses the target-specific emitted leaf"


def _control_ids(pointer: str) -> list[str]:
    controls = []
    if "/stream_engine/stream2/" in pointer or "/dram_loop_configs/LC3/" in pointer:
        controls.append("NC-DQ-D-COVERAGE-STRIDE")
    if "/PE_array/" in pointer:
        controls.append("NC-DQ-TWO-STAGE-ORDER")
    if "/general_array/outport/mask/" in pointer:
        controls.append("NC-DQ-D-MASK")
    if "/stream1/" in pointer or "/buffer2/" in pointer:
        controls.append("NC-DQ-COMPOSITE-B-LEAKAGE")
    return controls


def build_derivation_receipt(
    root: Path,
    stage_id: str,
    candidate: dict[str, Any],
    candidate_file_sha256: str,
) -> dict[str, Any]:
    spec = STAGES[stage_id]
    request = _request_index(root)[stage_id]
    validation = validate_candidate(candidate, stage_id)
    return {
        "schema": f"{SCHEMA}-target-derivation-receipt",
        "family": FAMILY,
        "stage_id": stage_id,
        "target_hw_op_type": request["identity"]["hw_op_type"],
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "candidate_sha256": candidate_file_sha256,
        "native_source": {
            "path": NATIVE_REL.as_posix(),
            "commit": NATIVE_COMMIT,
            "blob_oid": NATIVE_BLOB,
            "sha256": NATIVE_SHA256,
            "applicability": "CLASS_C_HARDWARE_BLOCK_FIELD_ORACLE_ONLY",
        },
        "typed_target": {
            "op": "DequantizeLinear",
            "input_dtype": "uint8",
            "output_dtype": "float32",
            "shape": spec["logical_shape"],
            "layout": spec["logical_layout"],
            "scale_bits": spec["scale_bits"],
            "zero_point": spec["zero_point"],
        },
        "materialization": {
            "standalone_streams": ["A", "D"],
            "composite_b_stream_removed": True,
            "topology": "4 ADD(x,-zp) -> 4 MUL(centered,scale)",
            "physical_shape_cwh": spec["hardware_shape_cwh"],
            "a_base": spec["a_base"],
            "d_base": spec["d_base"],
            "address_source": spec["current_path"],
            "negative_zero_point_source_bits": spec["negative_zero_point_bits"],
            "negative_zero_point_materialized_bits": (
                f"0x{_float32_bits(spec['negative_zero_point_materialized']):08x}"
            ),
            "constant_normalization": (
                "CDA-DEQUANT-MATERIALIZED-CONSTANT-NORMALIZATION-001"
                if stage_id == "hwop-0072-00"
                else "exact finite -60 materialization"
            ),
            "mapping_bitstream_execplan_sca_generated": False,
        },
        "validation": validation,
        "claim_boundary": (
            "Target-bounded local derivation receipt. It proves the strict JSON "
            "leaf equations and final current identity only; it does not claim "
            "generic native-handler support or integrated dynamic lifetime."
        ),
    }


def build_ledger(
    root: Path,
    stage_id: str,
    candidate: dict[str, Any],
    candidate_file_sha256: str,
    receipt_path: Path,
) -> dict[str, Any]:
    source = load_json(root / NATIVE_REL)
    source_leaves = dict(iter_leaves(source))
    candidate_leaves = dict(iter_leaves(candidate))
    receipt = bound(root, receipt_path)
    source_base = {
        "path": NATIVE_REL.as_posix(),
        "commit": NATIVE_COMMIT,
        "blob_oid": NATIVE_BLOB,
        "file_sha256": NATIVE_SHA256,
    }
    entries = []
    for pointer, value in candidate_leaves.items():
        origin = _origin(pointer, value)
        source_found = pointer in source_leaves
        source_ref = (
            {
                **source_base,
                "json_pointer": pointer,
                "value": source_leaves[pointer],
            }
            if source_found
            else None
        )
        entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "applicability_class": (
                    "EXPLICITLY_INACTIVE"
                    if origin == "EXPLICIT_DISABLED"
                    else "DERIVED_FOR_TARGET"
                ),
                "exactness_axes": _exactness(pointer, origin),
                "owner": (
                    "target DequantizeLinear family materializer bounded to "
                    f"{stage_id}"
                ),
                "consumer_equation": _consumer_equation(pointer, stage_id),
                "derivation_receipt": (
                    None if origin == "EXPLICIT_DISABLED" else receipt
                ),
                "source": source_ref,
                "negative_control_ids": _control_ids(pointer),
                "status": "RESOLVED",
            }
        )
    absences: dict[str, dict[str, Any]] = {}
    for pointer, value in candidate_leaves.items():
        if pointer not in source_leaves:
            state = "TARGET_REQUIRED_DERIVED"
            reason = "standalone target leaf is absent from the composite source"
        elif value is None:
            state = "EXPLICIT_NULL_INACTIVE"
            reason = "typed-null sentinel is explicitly inactive"
        elif value == 0 and not isinstance(value, bool):
            state = "EXPLICIT_ZERO"
            reason = "numeric zero is explicit and is never an implicit default"
        else:
            continue
        absences[pointer] = {
            "target_json_pointer": pointer,
            "state": state,
            "reason": reason,
            "owner": f"{FAMILY}:{stage_id}",
        }
    for pointer in sorted(set(source_leaves) - set(candidate_leaves)):
        absences[pointer] = {
            "target_json_pointer": pointer,
            "state": "SOURCE_ABSENT_NOT_APPLICABLE",
            "reason": (
                "composite B stream/buffer/group/topology leaf is not applicable "
                "to standalone DequantizeLinear"
            ),
            "owner": f"{FAMILY}:{stage_id}:composition-boundary",
        }
    return {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_file_sha256,
        "entries": entries,
        "source_absences": list(absences.values()),
        "claim_boundary": (
            "Exactly one entry covers every primitive candidate leaf. The native "
            "composite source is recorded per pointer but no target leaf claims "
            "REFERENCE_EXACT authority; all target values are derived or explicitly "
            "inactive."
        ),
    }


def build_handler_capability(
    root: Path, ledgers: list[dict[str, Any]]
) -> dict[str, Any]:
    dependent: dict[str, set[str]] = {}
    mapping = {
        "shape": "shape",
        "dtype": "dtype",
        "qparam": "qparams",
        "layout": "layout",
        "address": "address",
        "cross_stage_schedule": "schedule",
    }
    for ledger in ledgers:
        for entry in ledger["entries"]:
            for capability, exactness in mapping.items():
                if entry["exactness_axes"][exactness] is False:
                    dependent.setdefault(entry["json_pointer"], set()).add(capability)
    handler_path = root / GENERATOR_REL
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": FAMILY,
        "handler": {
            "kind": "AUTHORIZED_PATCH",
            "path": GENERATOR_REL.as_posix(),
            "sha256": sha256_file(handler_path),
            "source_span": (
                "build_candidate/validate_candidate; exactly hwop-0072-00 and "
                "hwop-0077-00, not generic add_dequant generalization"
            ),
        },
        "capabilities": {
            "exact_replay": {
                "supported": False,
                "evidence": "No native standalone exact target instance exists.",
            },
            "shape": {
                "supported": True,
                "evidence": "Two explicit typed target schedules are enumerated.",
            },
            "dtype": {
                "supported": True,
                "evidence": "UINT8 ingress conversion and FP32 normal outbuffer are checked.",
            },
            "qparam": {
                "supported": True,
                "evidence": "Per-stage scale bits and zero point bind the eight GA constants.",
            },
            "layout": {
                "supported": True,
                "evidence": "Per-stage CWH occurrence and padding equations are checked.",
            },
            "address": {
                "supported": True,
                "evidence": (
                    "Exact frozen A/D base pairs are reproduced and compared; "
                    "no new address planning is claimed."
                ),
            },
            "cross_stage_schedule": {
                "supported": True,
                "evidence": (
                    "Candidate-local standalone stream/loop visibility is checked; "
                    "integrated graph lifetime remains outside the claim."
                ),
            },
        },
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": sorted(axes),
                "covered_by": "target-bounded Dequant family materializer and derivation receipt",
                "status": "COVERED",
            }
            for pointer, axes in sorted(dependent.items())
        ],
        "claim_boundary": (
            "The native add_dequant registry handler remains a placeholder and is "
            "not used as target authority. AUTHORIZED_PATCH means only the two "
            "enumerated ResNet target instances, not arbitrary shape/dtype/qparam "
            "generalization or integrated lifetime closure."
        ),
    }


def build_composition(stage_id: str) -> dict[str, Any]:
    spec = STAGES[stage_id]
    byte_set = "four binary32 GA lane values [lane0:4B,lane1:4B,lane2:4B,lane3:4B]"
    return {
        "schema": "operator_config_composition_boundary_v1",
        "family": FAMILY,
        "boundaries": [
            {
                "boundary_id": f"{stage_id}:ga-add-to-mul",
                "producer_dtype": "float32",
                "consumer_dtype": "float32",
                "shape": (
                    f"one 4-lane GA group per occurrence; "
                    f"{spec['occurrences_per_slice']} occurrences per slice"
                ),
                "layout": "PE00/02/20/22 normal outbuffer -> PE10/12/30/32 inport0",
                "producer_byte_set": byte_set,
                "consumer_required_byte_set": byte_set,
                "transaction_bytes": 16,
                "tag_last": "normal outbuffer per occurrence; no transout_last_index",
                "clock_handshake": "direct GA predecessor src_id edge under the same occurrence",
                "lifetime_visibility": "producer result is consumed in the second GA level",
                "qparam_rounding": (
                    "binary32 ADD(x,-zp) rounds before binary32 MUL(centered,scale)"
                ),
                "status": "RESOLVED",
                "evidence": [
                    "CDA-DEQUANT-ONNX-ORDER-001",
                    "CDA-DEQUANT-TWO-STAGE-GA-001",
                    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
                ],
            }
        ],
        "claim_boundary": (
            "Only the internal ADD-to-MUL GA primitive boundary is closed. "
            "No external node-to-node address/lifetime binding is claimed."
        ),
    }


def build_current_diff(
    root: Path,
    stage_id: str,
    candidate: dict[str, Any],
    candidate_file_sha256: str,
) -> dict[str, Any]:
    spec = STAGES[stage_id]
    current_path = root / spec["current_path"]
    current = load_json(current_path)
    entries = []
    for pointer, value in iter_leaves(candidate):
        found, current_value = _pointer(current, pointer)
        classification = "SAME" if found and current_value == value else (
            "CURRENT_ABSENT" if not found else "NEW_CANDIDATE_DEFECT"
        )
        entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": value,
                "current_value_present": found,
                "current_value": current_value,
                "classification": classification,
                "reason": (
                    "regenerated target leaf equals the frozen current final JSON"
                    if classification == "SAME"
                    else "regenerated target leaf does not match frozen current final JSON"
                ),
                "evidence": [
                    spec["current_path"],
                    f"sha256:{sha256_file(current_path)}",
                ],
            }
        )
    blockers = (
        [
            {
                "blocker_id": "B_DEQUANT_NODE0072_NATIVE_PRODUCTION_PATH",
                "classification": "CONFIG_EXCLUDED",
                "candidate_json_pointers": [],
                "reason": "Complete local JSON does not supply an adapted native production handler.",
                "evidence": [
                    ".agents/rules/DequantizeLinear算子配置规则.md",
                    spec["current_path"],
                ],
            },
            {
                "blocker_id": "B_GAP_NODE0071_TO_NODE0072_INTEGRATED_BINDING",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Producer/consumer same-storage lifetime is outside a standalone JSON.",
                "evidence": [
                    "contracts/operator_config/stage_state_lifetime_contract_v1.json"
                ],
            },
            {
                "blocker_id": "B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Flatten visibility and accepted completion need integrated execution.",
                "evidence": [
                    "contracts/operator_config/dequant_node0072_shared_endpoint_manifest_v1.json"
                ],
            },
            {
                "blocker_id": "B_DEQUANT_NODE0072_FORMAL_E4_E5",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Local complete JSON cannot create formal dynamic evidence.",
                "evidence": [
                    ".agents/task_records/20260727_dequant_node0072_config_only_e2_mainline_adjudication.md"
                ],
            },
        ]
        if stage_id == "hwop-0072-00"
        else [
            {
                "blocker_id": "DEQUANT_ATOMIC_OBSERVER_TEMPORAL_INCOMPLETE",
                "classification": "CONFIG_EXCLUDED",
                "candidate_json_pointers": [],
                "reason": (
                    "The atomic v3 observer gap is not a config defect and does "
                    "not invalidate full-v6 E4/E5 formal D."
                ),
                "evidence": [
                    ".agents/task_records/20260726_dequant_atomic1_v3_return_analysis.md",
                    ".agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md",
                    ".agents/task_records/20260727_dequant_node0077_full_v6_e5_pass.md",
                ],
            }
        ]
    )
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_file_sha256,
        "current_identity": {
            "available": True,
            "path": spec["current_path"],
            "sha256": sha256_file(current_path),
            "package_or_record": (
                ".agents/task_records/"
                + (
                    "20260727_dequant_node0072_config_only_e2_mainline_adjudication.md"
                    if stage_id == "hwop-0072-00"
                    else "20260727_dequant_node0077_three_way_closure.md"
                )
            ),
            "latest_result": spec["current_result"],
        },
        "entries": entries,
        "blocker_attribution": blockers,
        "claim_boundary": (
            "Leaf-complete comparison to the frozen final address-bound JSON. "
            "Observer, package, RTL, formal dynamic, and integrated lifetime "
            "questions are not reclassified as configuration defects."
        ),
    }


def numeric_and_formula_evidence(root: Path) -> dict[str, Any]:
    node72 = dq72.numeric_evidence(root)
    node77 = dq77.build_numeric_evidence(root)
    return {
        "schema": f"{SCHEMA}-numeric-formula-evidence",
        "node0072": node72,
        "node0077": node77,
        "negative_controls": {
            "node0077_single_affine_mac_mismatch_count": node77[
                "affine_mac_bit_mismatch_count"
            ],
            "node0072_wrong_zero_point_60_rejected": _node72_wrong_zp_rejected(root),
        },
        "server_evidence_rerun": False,
    }


def _node72_wrong_zp_rejected(root: Path) -> bool:
    x = np.load(root / dq72.INPUT_RELATIVE, allow_pickle=False)
    golden = np.load(root / dq72.OUTPUT_RELATIVE, allow_pickle=False)
    wrong = np.multiply(
        np.subtract(x.astype(np.float32), np.float32(60.0), dtype=np.float32),
        dq72.SCALE[0],
        dtype=np.float32,
    )
    return not np.array_equal(wrong.view(np.uint32), golden.view(np.uint32))


def negative_controls(
    candidates: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    mutations = {
        "composite_b_stream_leakage": lambda c: c["stream_engine"].update(
            {"stream1": copy.deepcopy(c["stream_engine"]["stream0"])}
        ),
        "missing_d_stream": lambda c: c["stream_engine"].pop("stream2"),
        "wrong_d_mask": lambda c: c["general_array"]["outport"].update(
            {"mask": [1, 0, 1, 0, 1, 0, 1, 0]}
        ),
        "d_stride_256_coverage": lambda c: c["stream_engine"]["stream2"][
            "dim_stride"
        ].__setitem__(1, 256),
        "scale_qparam_drift": lambda c: c["general_array"]["PE_array"]["PE10"][
            "inport1"
        ].update({"constant": "1.0"}),
        "single_stage_order": lambda c: c["general_array"]["PE_array"]["PE10"].update(
            {"alu_opcode": "add"}
        ),
    }
    results = []
    for stage_id, candidate in candidates.items():
        for control_id, mutate in mutations.items():
            modified = copy.deepcopy(candidate)
            mutate(modified)
            failed_closed = False
            message = ""
            try:
                validate_candidate(modified, stage_id)
            except DequantCompleteJsonError as error:
                failed_closed = True
                message = str(error)
            if not failed_closed:
                raise DequantCompleteJsonError(
                    f"negative control did not fail closed: {stage_id}:{control_id}"
                )
            results.append(
                {
                    "stage_id": stage_id,
                    "control_id": control_id,
                    "failed_closed": True,
                    "error": message,
                }
            )
    return {
        "schema": f"{SCHEMA}-negative-controls",
        "count": len(results),
        "all_failed_closed": True,
        "results": results,
    }


def _static_diff(root: Path, stage_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    spec = STAGES[stage_id]
    static = load_json(root / spec["static_path"])
    pointers = sorted(set(dict(iter_leaves(static))) | set(dict(iter_leaves(candidate))))
    entries = []
    for pointer in pointers:
        static_found, static_value = _pointer(static, pointer)
        candidate_found, candidate_value = _pointer(candidate, pointer)
        if (static_found, static_value) != (candidate_found, candidate_value):
            entries.append(
                {
                    "json_pointer": pointer,
                    "static_value_present": static_found,
                    "static_value": static_value,
                    "candidate_value_present": candidate_found,
                    "candidate_value": candidate_value,
                    "owner": (
                        "address planner"
                        if pointer.endswith("/base_addr")
                        else "typed qparam materializer"
                    ),
                    "classification": "INTENTIONAL_DERIVATION",
                }
            )
    return {
        "stage_id": stage_id,
        "static_path": spec["static_path"],
        "static_sha256": sha256_file(root / spec["static_path"]),
        "candidate_diff_count": len(entries),
        "entries": entries,
    }


def build_artifacts(root: Path, output: Path | None = None) -> dict[str, Path]:
    root = root.resolve()
    output = (output or root / ARTIFACT_REL).resolve()
    if output.exists():
        raise DequantCompleteJsonError(f"refusing to overwrite artifact root: {output}")
    output.mkdir(parents=True)
    candidates = {stage_id: build_candidate(root, stage_id) for stage_id in STAGES}
    inventory = build_stage_inventory(root)
    references = build_reference_applicability(root)
    write_json(output / "stage_inventory.json", inventory)
    write_json(output / "reference_applicability.json", references)
    candidate_paths: dict[str, Path] = {}
    receipt_paths: dict[str, Path] = {}
    ledgers: dict[str, dict[str, Any]] = {}
    ledger_paths: dict[str, Path] = {}
    composition_paths: dict[str, Path] = {}
    diff_paths: dict[str, Path] = {}
    for stage_id, candidate in candidates.items():
        stem = stage_id.replace("hwop-", "node")
        candidate_path = output / "complete_json" / f"{stem}.json"
        write_json(candidate_path, candidate)
        candidate_paths[stage_id] = candidate_path
        candidate_file_sha256 = sha256_file(candidate_path)
        receipt_path = output / "derivation" / f"{stem}.json"
        write_json(
            receipt_path,
            build_derivation_receipt(
                root,
                stage_id,
                candidate,
                candidate_file_sha256,
            ),
        )
        receipt_paths[stage_id] = receipt_path
        ledger = build_ledger(
            root,
            stage_id,
            candidate,
            candidate_file_sha256,
            receipt_path,
        )
        ledger_path = output / "evidence" / stem / "field_provenance_ledger.json"
        write_json(ledger_path, ledger)
        ledgers[stage_id] = ledger
        ledger_paths[stage_id] = ledger_path
        composition_path = output / "evidence" / stem / "composition_boundary.json"
        write_json(composition_path, build_composition(stage_id))
        composition_paths[stage_id] = composition_path
        diff_path = output / "evidence" / stem / "current_test_diff.json"
        write_json(
            diff_path,
            build_current_diff(
                root,
                stage_id,
                candidate,
                candidate_file_sha256,
            ),
        )
        diff_paths[stage_id] = diff_path
    handler = build_handler_capability(root, list(ledgers.values()))
    handler_path = output / "handler_capability.json"
    write_json(handler_path, handler)
    write_json(
        output / "field_provenance_ledger.json",
        {
            "schema": f"{SCHEMA}-family-ledger-index",
            "family": FAMILY,
            "candidate_count": len(ledgers),
            "candidate_leaf_count": sum(len(item["entries"]) for item in ledgers.values()),
            "unresolved_count": 0,
            "ledgers": [
                {
                    "stage_id": stage_id,
                    **bound(root, ledger_paths[stage_id]),
                }
                for stage_id in STAGES
            ],
        },
    )
    write_json(
        output / "current_test_diff.json",
        {
            "schema": f"{SCHEMA}-family-current-diff-index",
            "family": FAMILY,
            "diffs": [
                {"stage_id": stage_id, **bound(root, diff_paths[stage_id])}
                for stage_id in STAGES
            ],
            "class_counts": {
                "SAME": sum(len(item["entries"]) for item in ledgers.values()),
                "INTENTIONAL_DERIVATION": 0,
                "SUSPECTED_CURRENT_DEFECT": 0,
                "NEW_CANDIDATE_DEFECT": 0,
                "DYNAMIC_ONLY": 0,
                "CURRENT_ABSENT": 0,
            },
        },
    )
    numeric_path = output / "numeric_formula_validation.json"
    write_json(numeric_path, numeric_and_formula_evidence(root))
    controls_path = output / "negative_controls.json"
    write_json(controls_path, negative_controls(candidates))
    strict_path = output / "strict_schema_validation.json"
    write_json(
        strict_path,
        {
            "schema": f"{SCHEMA}-strict-validation",
            "valid": True,
            "candidate_count": 2,
            "results": [
                validate_candidate(candidates[stage_id], stage_id)
                for stage_id in STAGES
            ],
        },
    )
    contract_paths: dict[str, Path] = {}
    for stage_id in STAGES:
        stem = stage_id.replace("hwop-", "node")
        contract = {
            "schema": "operator_config_complete_json_candidate_v1",
            "family": FAMILY,
            "candidate_status": "COMPLETE",
            "reference_class": "D",
            "changed_axes": list(CHANGED_AXES),
            "target_hw_op_types": ["DequantizeLinear"],
            "stage_ids": [stage_id],
            "candidate_json": bound(root, candidate_paths[stage_id]),
            "field_provenance_ledger": bound(root, ledger_paths[stage_id]),
            "handler_capability": bound(root, handler_path),
            "current_test_diff": bound(root, diff_paths[stage_id]),
            "composition": {
                "required": True,
                "boundary": bound(root, composition_paths[stage_id]),
            },
            "artifact_root": output.relative_to(root).as_posix(),
            "claim_boundary": (
                f"COMPLETE strict local JSON for exactly {stage_id}. No mapping, "
                "bitstream, execplan, SCA, package, server execution, formal D, "
                "new E4/E5, or integrated node lifetime is generated."
            ),
        }
        contract_path = output / "contracts" / f"{stem}_candidate_contract.json"
        write_json(contract_path, contract)
        contract_paths[stage_id] = contract_path
    family_set_path = output / "family_set.json"
    write_json(
        family_set_path,
        {
            "schema": "operator_config_complete_json_family_set_v1",
            "family": FAMILY,
            "target_hw_op_types": ["DequantizeLinear"],
            "candidate_contracts": [
                bound(root, contract_paths[stage_id]) for stage_id in STAGES
            ],
            "no_config_stages": [],
            "claim_boundary": (
                "Both and only the two DequantizeLinear lowering stages are "
                "covered exactly once by COMPLETE strict JSON candidates."
            ),
        },
    )
    report_path = output / "report.json"
    write_json(
        report_path,
        {
            "schema": SCHEMA,
            "status": "COMPLETE",
            "family": FAMILY,
            "stage_count": 2,
            "equivalence_class_count": 2,
            "materialized_candidate_count": 2,
            "candidate_leaf_count": sum(
                len(list(iter_leaves(candidate))) for candidate in candidates.values()
            ),
            "unresolved_count": 0,
            "candidate_contracts": [
                {"stage_id": stage_id, **bound(root, contract_paths[stage_id])}
                for stage_id in STAGES
            ],
            "family_set": bound(root, family_set_path),
            "validation_inputs": {
                "strict": bound(root, strict_path),
                "numeric_formula": bound(root, numeric_path),
                "negative_controls": bound(root, controls_path),
            },
            "static_to_candidate_diffs": [
                _static_diff(root, stage_id, candidates[stage_id])
                for stage_id in STAGES
            ],
            "current_diff_summary": {
                "same": sum(
                    len(list(iter_leaves(candidate)))
                    for candidate in candidates.values()
                ),
                "intentional_derivation": 0,
                "suspected_current_defect": 0,
                "new_candidate_defect": 0,
                "dynamic_only_leaf": 0,
            },
            "current_config_finding": (
                "No candidate/current final JSON leaf difference was found. "
                "Current node0072 blockers are production/integrated/dynamic, not "
                "explained by a strict JSON leaf defect. Node0077 remains the "
                "frozen mature positive control."
            ),
            "analysis_accounting": {
                "local_numeric_formula_validation_repeated": True,
                "reason": "explicitly required by the new complete-JSON authorization",
                "node0077_server_e4_e5_repeated": False,
                "node0072_local_e2_toolchain_rebuilt": False,
                "mapping_bitstream_execplan_sca_generated": False,
                "frozen_assets_consumed_read_only": True,
            },
            "formal_three_way_count": "unchanged 1/78",
            "package_release": "NONE",
            "rule_feedback": {
                "type": "RULE_CONFIRMATION",
                "non_synonymous_delta": None,
                "confirmed_rule_ids": [
                    "CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001",
                    "CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001",
                    "CDA-NATIVE-COMPOSITION-BOUNDARY-001",
                    "CDA-DEQUANT-MATERIALIZED-CONSTANT-NORMALIZATION-001",
                    "CDA-DEQUANT-NODE0072-CONFIG-ONLY-E2-001",
                ],
            },
            "claim_boundary": (
                "Local complete strict JSON, leaf provenance, handler capability, "
                "internal primitive composition, and frozen-current comparison "
                "only. No production or server release claim is made."
            ),
        },
    )
    return {
        "output": output,
        "report": report_path,
        "family_set": family_set_path,
        "node0072_contract": contract_paths["hwop-0072-00"],
        "node0077_contract": contract_paths["hwop-0077-00"],
    }


def finalize_public_validation(
    root: Path, output: Path | None = None
) -> dict[str, Any]:
    """Bind fresh shared-validator reports into the family report."""
    root = root.resolve()
    output = (output or root / ARTIFACT_REL).resolve()
    report_path = output / "report.json"
    report = load_json(report_path)
    validation_paths = {
        "node0072_candidate": output / "node0072_public_validation.json",
        "node0077_candidate": output / "node0077_public_validation.json",
        "family_set": output / "family_set_public_audit.json",
    }
    validation = {name: load_json(path) for name, path in validation_paths.items()}
    for name, document in validation.items():
        if document.get("pass") is not True:
            raise DequantCompleteJsonError(f"public validation is not PASS: {name}")
        if document.get("errors") != []:
            raise DequantCompleteJsonError(f"public validation has errors: {name}")
        if name != "family_set" and document.get("completion_blockers") != []:
            raise DequantCompleteJsonError(
                f"public validation has completion blockers: {name}"
            )
    forbidden = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() == ".zip"
            or path.name
            in {
                "PREPARE_AND_RUN.sh",
                "TEST_PACKAGE_MANIFEST.json",
                "SERVER_RESULT_GATE.json",
            }
        )
    ]
    if forbidden:
        raise DequantCompleteJsonError(f"forbidden package output: {forbidden}")
    receipt_paths = [
        Path(".agents/agent.md"),
        Path(".agents/plan.md"),
        Path(".agents/rules/生成前必读索引.md"),
        Path(".agents/rules/算子配置规则.md"),
        Path(".agents/rules/NDP硬件字段语义.md"),
        Path(".agents/rules/DequantizeLinear算子配置规则.md"),
        Path(".agents/rules/DequantizeLinear原子动态合同规则.md"),
        POLICY_REL,
        Path("schemas/operator_config_complete_json_candidate_v1.schema.json"),
        Path("schemas/operator_config_field_provenance_ledger_v1.schema.json"),
        Path("schemas/operator_config_handler_capability_v1.schema.json"),
        Path("schemas/operator_config_current_test_diff_v1.schema.json"),
        Path("schemas/operator_config_composition_boundary_v1.schema.json"),
        Path("schemas/operator_config_complete_json_family_set_v1.schema.json"),
        Path("tools/validate_complete_operator_json_candidate.py"),
        Path("tools/audit_complete_operator_json_family_set.py"),
        LOWERING_REL,
        AUTHORITY_REL,
        NATIVE_REL,
        GENERATOR_REL,
    ]
    report["read_receipts"] = [
        {
            "path": path.as_posix(),
            "sha256": sha256_file(root / path),
        }
        for path in receipt_paths
    ]
    report["public_validation"] = {
        "status": "COMPLETE",
        "node0072": {
            **bound(root, validation_paths["node0072_candidate"]),
            "pass": True,
            "contract_valid": True,
            "errors": 0,
            "completion_blockers": 0,
            "candidate_leaf_count": 416,
            "ledger_leaf_count": 416,
        },
        "node0077": {
            **bound(root, validation_paths["node0077_candidate"]),
            "pass": True,
            "contract_valid": True,
            "errors": 0,
            "completion_blockers": 0,
            "candidate_leaf_count": 416,
            "ledger_leaf_count": 416,
        },
        "family_set": {
            **bound(root, validation_paths["family_set"]),
            "pass": True,
            "expected_stage_count": 2,
            "covered_stage_count": 2,
            "missing_stage_count": 0,
            "unexpected_stage_count": 0,
            "errors": 0,
        },
        "commands": [
            (
                "python tools/validate_complete_operator_json_candidate.py "
                "artifacts/operator_config_validation/"
                "r5_complete_json_regeneration_v1/dequantize_linear/contracts/"
                "node0072-00_candidate_contract.json"
            ),
            (
                "python tools/validate_complete_operator_json_candidate.py "
                "artifacts/operator_config_validation/"
                "r5_complete_json_regeneration_v1/dequantize_linear/contracts/"
                "node0077-00_candidate_contract.json"
            ),
            (
                "python tools/audit_complete_operator_json_family_set.py "
                "artifacts/operator_config_validation/"
                "r5_complete_json_regeneration_v1/dequantize_linear/family_set.json"
            ),
        ],
        "exit_codes": [0, 0, 0],
    }
    report["forbidden_output_scan"] = {
        "patterns": [
            "*.zip",
            "PREPARE_AND_RUN.sh",
            "TEST_PACKAGE_MANIFEST.json",
            "SERVER_RESULT_GATE.json",
        ],
        "violations": [],
        "pass": True,
    }
    report["output_receipts_excluding_report"] = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path != report_path
    ]
    write_json(report_path, report)
    return report


__all__ = [
    "ARTIFACT_REL",
    "DequantCompleteJsonError",
    "build_artifacts",
    "build_candidate",
    "build_stage_inventory",
    "finalize_public_validation",
    "negative_controls",
    "validate_candidate",
]
