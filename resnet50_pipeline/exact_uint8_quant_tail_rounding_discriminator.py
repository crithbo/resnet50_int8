"""Build and validate the config-bound 26-vs-25 quant-tail discriminator.

The bundle is deliberately diagnostic-only.  It materializes two native JSON
configurations separated by FP32 scratch so the multiplier rounding point is
not contracted into the magic-bias MAC.  It does not generate a mapping,
bitstream, execplan, SCA, target instance, or server package.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.exact_uint8_quant_tail_capability import (
    one_round_fused_magic,
    proposed_subtract_patch,
    sequential_multiplier_tail,
)


SCHEMA = "exact-uint8-quant-tail-rounding-discriminator-v1"
REPORT_SCHEMA = "exact-uint8-quant-tail-rounding-discriminator-report-v1"
MANIFEST_SCHEMA = "exact-uint8-quant-tail-rounding-discriminator-manifest-v1"
MAGIC_BITS = 0x4B400000
MAGIC_FLOAT = np.float32(12582912.0)
DISCRIMINATOR_MULTIPLIER_BITS = 0x3D828F5C
DISCRIMINATOR_MULTIPLIER = np.asarray(
    DISCRIMINATOR_MULTIPLIER_BITS, dtype=np.uint32
).view(np.float32)
EVEN_PES = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
ODD_PES = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
CONFIG_FILENAMES = (
    "stage0_mul_to_fp32_scratch.json",
    "stage1_magic_decode_to_uint8.json",
    "negative_control_fused.json",
)
OWNERSHIP_FILENAME = "materialized_leaf_ownership.json"


class RoundingDiscriminatorError(ValueError):
    """Raised when the config-bound discriminator no longer proves 26-vs-25."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _f32_bits(value: float) -> int:
    return int(np.asarray(np.float32(value), dtype=np.float32).view(np.uint32))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RoundingDiscriminatorError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _flatten_json(value: Any, path: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    if isinstance(value, dict):
        if not value:
            leaves[path or "/"] = {}
        for key in sorted(value):
            escaped = key.replace("~", "~0").replace("/", "~1")
            leaves.update(_flatten_json(value[key], f"{path}/{escaped}"))
    elif isinstance(value, list):
        if not value:
            leaves[path or "/"] = []
        for index, item in enumerate(value):
            leaves.update(_flatten_json(item, f"{path}/{index}"))
    else:
        leaves[path or "/"] = value
    return leaves


def _leaf_diff(base: dict[str, Any], final: dict[str, Any]) -> list[dict[str, Any]]:
    before = _flatten_json(base)
    after = _flatten_json(final)
    absent = {"$absent": True}
    result = []
    for path in sorted(set(before) | set(after)):
        old = before.get(path, absent)
        new = after.get(path, absent)
        if old != new:
            result.append(
                {
                    "path": path,
                    "old_value": old,
                    "expected_new_value": new,
                }
            )
    return result


def _authorize_leaf_diff(
    config_name: str, item: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    path = item["path"]
    if path.startswith("/stream_engine/") and path.endswith("/base_addr"):
        declaration = {
            "owner": "planner/address binder",
            "input_source": "stage_contract input_address/output_address",
            "formula": "explicit diagnostic region base selected from stage DAG; no inherited server or package address",
            "authorization": "CDA-CONFIG-SEMANTIC-OWNERSHIP-001 plus this diagnostic stage_contract",
            "base_field": True,
        }
    elif path.startswith(
        ("/dram_loop_configs/", "/buffer_loop_configs/", "/stream_engine/")
    ):
        declaration = {
            "owner": "logical ScheduleIR",
            "input_source": "transaction_contract logical_element_count=32, ga_lane_count=8, issue_cycles=4 and pack_factor=4",
            "formula": "one 32-element occurrence; FP32 stage emits four 32-byte transactions, UINT8 stage emits one packed 32-byte transaction",
            "authorization": "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001 plus transaction_contract",
            "base_field": False,
        }
    elif path.startswith("/general_array/"):
        declaration = {
            "owner": "operator numeric/layout contract",
            "input_source": "discriminator bits, stage_contract numeric order, zero_point and HWC8 lane mapping",
            "formula": "stage0=MUL then FP32 materialization; stage1=MAC(x,1.0,magic), INT32_SUB(magic_bits-zp), UINT8 saturation; negative control=fused MAC",
            "authorization": "CDA-EXACT-UINT8-QUANT-TAIL-ORDER-001 and CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "base_field": False,
        }
    else:
        raise RoundingDiscriminatorError(
            f"unowned materialized leaf diff in {config_name}: {path}"
        )
    return {
        "config": config_name,
        **item,
        **declaration,
        "rule_id": contract["materialized_leaf_ownership_policy"]["rule_id"],
    }


def _build_leaf_ownership(
    oracle: dict[str, Any],
    configs: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    declarations = []
    per_config_count: dict[str, int] = {}
    for name in CONFIG_FILENAMES:
        diff = _leaf_diff(oracle, configs[name])
        owned = [_authorize_leaf_diff(name, item, contract) for item in diff]
        declarations.extend(owned)
        per_config_count[name] = len(owned)
    return {
        "schema": "exact-uint8-quant-tail-materialized-leaf-ownership-v1",
        "rule_id": contract["materialized_leaf_ownership_policy"]["rule_id"],
        "trusted_static_config": contract["configuration_oracle"],
        "diff_granularity": "leaf",
        "declaration_count": len(declarations),
        "per_config_count": per_config_count,
        "declarations": declarations,
        "unknown_diff_action": "fail closed",
        "multiple_owner_action": "fail closed",
    }


def _parse_address(value: str) -> int:
    try:
        return int(value, 0)
    except (TypeError, ValueError) as exc:
        raise RoundingDiscriminatorError(
            f"diagnostic requires explicit hex base address, got {value!r}"
        ) from exc


def _materialized_output_coverage(
    config_name: str, config: dict[str, Any], expected_region_bytes: int
) -> dict[str, Any]:
    """Recompute byte coverage from the final output occurrence equation."""

    loop = config["dram_loop_configs"]["LC2"]
    start = int(loop["start"])
    end = int(loop["end"])
    stride = int(loop["stride"])
    if stride <= 0 or end <= start or (end - start) % stride:
        raise RoundingDiscriminatorError(
            f"invalid final LC2 output occurrence domain: {config_name}"
        )
    occurrence_values = list(range(start, end, stride))
    transaction_bytes = 8 * 4
    address_stride = int(config["stream_engine"]["stream2"]["dim_stride"][0])
    if address_stride != transaction_bytes:
        raise RoundingDiscriminatorError(
            f"non-contiguous output transaction stride in {config_name}: "
            f"{address_stride} != {transaction_bytes}"
        )
    base = _parse_address(config["stream_engine"]["stream2"]["base_addr"])
    covered = set()
    transaction_bases = []
    for occurrence in occurrence_values:
        transaction_base = base + occurrence * address_stride
        transaction_bases.append(transaction_base)
        covered.update(range(transaction_base, transaction_base + transaction_bytes))
    expected = set(range(base, base + expected_region_bytes))
    if covered != expected:
        raise RoundingDiscriminatorError(
            f"final output byte coverage mismatch in {config_name}: "
            f"covered={len(covered)} expected={len(expected)}"
        )
    return {
        "config": config_name,
        "equation": "addr=stream2.base_addr+LC2_value*stream2.dim_stride[0]+byte_in_32B_transaction",
        "occurrence_values": occurrence_values,
        "transaction_bytes": transaction_bytes,
        "transaction_bases": [f"0x{value:x}" for value in transaction_bases],
        "unique_written_byte_count": len(covered),
        "expected_region_byte_count": expected_region_bytes,
        "coverage_ratio": "1/1",
        "region": f"[0x{base:x},0x{base + expected_region_bytes:x})",
        "passed": True,
    }


def _set_stream_address(config: dict[str, Any], stream: str, address: str) -> None:
    config["stream_engine"][stream]["base_addr"] = address


def _set_single_occurrence_geometry(
    config: dict[str, Any], *, packed_uint8_output: bool
) -> None:
    """Materialize one 32-element occurrence.

    Four GA issue cycles feed eight lanes.  The FP32 form writes 32 words; the
    UINT8 form packs four issue cycles into eight output words.
    """

    loops = config["dram_loop_configs"]
    loops["LC0"].update({"end": 1, "last_index": 0})
    loops["LC1"].update({"end": 4, "last_index": 1})
    loops["LC2"].update(
        {"end": 1 if packed_uint8_output else 4, "last_index": 1}
    )

    group0 = config["buffer_loop_configs"]["GROUP0"]
    group0["ROW_LC"].update(
        {"src_id": "DRAM_LC.LC1", "end": 1, "stride": 1, "last_index": 2}
    )
    group0["COL_LC"].update({"end": 32, "stride": 16, "last_index": 3})

    group2 = config["buffer_loop_configs"]["GROUP2"]
    group2["ROW_LC"].update(
        {"src_id": "DRAM_LC.LC2", "end": 1, "stride": 1, "last_index": 2}
    )
    group2["COL_LC"].update(
        {
            "end": 4 if packed_uint8_output else 32,
            "stride": 2 if packed_uint8_output else 16,
            "last_index": 3,
        }
    )

    read = config["stream_engine"]["stream0"]
    read["idx_size"] = [0, 31, None]
    read["dim_stride"] = [32, 128, None]
    read["buf_spatial_stride"] = list(range(16))
    read["buf_spatial_size"] = 16

    write = config["stream_engine"]["stream2"]
    write["idx_size"] = [3, 7, None] if packed_uint8_output else [0, 31, None]
    write["dim_stride"] = [32, 32 if packed_uint8_output else 128, None]
    write["buf_spatial_stride"] = (
        [
            0,
            4,
            8,
            12,
            16,
            20,
            24,
            28,
            1,
            5,
            9,
            13,
            17,
            21,
            25,
            29,
        ]
        if packed_uint8_output
        else list(range(16))
    )
    write["buf_spatial_size"] = 16


def _set_conversion_flags(port: dict[str, Any], *, int32_to_fp32: bool) -> None:
    port.update(
        {
            "fp16tofp32": "false",
            "bf16tofp32": "false",
            "int32tofp32": "true" if int32_to_fp32 else "false",
            "uint8tofp32": "false",
            "uint8toint32": "false",
        }
    )


def _build_stage0(oracle: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(oracle)
    _set_single_occurrence_geometry(config, packed_uint8_output=False)
    _set_stream_address(config, "stream0", "0x0")
    _set_stream_address(config, "stream2", "0x800000")
    _set_conversion_flags(
        config["general_array"]["inport"]["inport0"], int32_to_fp32=True
    )
    config["general_array"]["outport"].update(
        {"src_id": 0, "int32touint8": "false"}
    )
    pe_array: dict[str, Any] = {}
    for name in EVEN_PES:
        pe = copy.deepcopy(oracle["general_array"]["PE_array"][name])
        pe["alu_opcode"] = "mul"
        pe["inport0"].update({"src_id": 0, "mode": "buffer"})
        pe["inport1"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": float(DISCRIMINATOR_MULTIPLIER),
            }
        )
        pe["inport2"].update({"src_id": None, "mode": None, "constant": 0})
        pe_array[name] = pe
    config["general_array"]["PE_array"] = pe_array
    return config


def _build_stage1(oracle: dict[str, Any], zero_point: int) -> dict[str, Any]:
    config = copy.deepcopy(oracle)
    _set_single_occurrence_geometry(config, packed_uint8_output=True)
    _set_stream_address(config, "stream0", "0x800000")
    _set_stream_address(config, "stream2", "0x1000000")
    _set_conversion_flags(
        config["general_array"]["inport"]["inport0"], int32_to_fp32=False
    )
    config["general_array"]["outport"].update(
        {"src_id": 1, "int32touint8": "true"}
    )
    for name in EVEN_PES:
        pe = config["general_array"]["PE_array"][name]
        pe["alu_opcode"] = "mac"
        pe["inport0"].update({"src_id": 0, "mode": "buffer"})
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "constant": 1.0}
        )
        pe["inport2"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": float(MAGIC_FLOAT),
            }
        )
    subtract = (MAGIC_BITS - int(zero_point)) & 0xFFFFFFFF
    for name in ODD_PES:
        pe = config["general_array"]["PE_array"][name]
        pe["alu_opcode"] = "int32_sub"
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "constant": subtract}
        )
    return config


def _build_negative_control(oracle: dict[str, Any], zero_point: int) -> dict[str, Any]:
    config = _build_stage1(oracle, zero_point)
    _set_stream_address(config, "stream0", "0x0")
    _set_stream_address(config, "stream2", "0x1800000")
    _set_conversion_flags(
        config["general_array"]["inport"]["inport0"], int32_to_fp32=True
    )
    for name in EVEN_PES:
        config["general_array"]["PE_array"][name]["inport1"]["constant"] = float(
            DISCRIMINATOR_MULTIPLIER
        )
    return config


def _validate_source_identities(
    project_root: Path, contract: dict[str, Any]
) -> list[dict[str, Any]]:
    validated = []
    for source in contract["semantic_source_identities"]:
        path = project_root / source["path"]
        if not path.is_file():
            raise RoundingDiscriminatorError(
                f"missing semantic source: {source['path']}"
            )
        actual = _sha256(path)
        if actual != source["sha256"]:
            raise RoundingDiscriminatorError(
                f"semantic source changed: {source['path']} "
                f"expected={source['sha256']} actual={actual}"
            )
        validated.append(
            {
                "path": source["path"],
                "sha256": actual,
                "gate": "current_match_fail_closed",
            }
        )
    return validated


def _validate_read_receipts(
    project_root: Path,
    contract: dict[str, Any],
    field: str = "read_receipt",
    gate: str = "historical_provenance_only",
) -> list[dict[str, Any]]:
    receipts = []
    for source in contract[field]:
        path = project_root / source["path"]
        current = _sha256(path) if path.is_file() else None
        receipts.append(
            {
                "path": source["path"],
                "recorded_sha256": source["sha256"],
                "current_sha256": current,
                "current_match": current == source["sha256"],
                "gate": gate,
            }
        )
    return receipts


def _validate_bypass_annotation(contract: dict[str, Any]) -> dict[str, Any]:
    annotation = contract["bypass_annotation"]
    required = (
        "bypass_reason",
        "contradicted_or_missing_native_path",
        "exact_equivalence_scope",
        "materialized_configuration_mechanism",
        "performance_and_resource_cost",
        "unresolved_production_blocker",
        "claim_boundary",
    )
    missing = [key for key in required if not annotation.get(key)]
    if missing:
        raise RoundingDiscriminatorError(
            f"missing config-only bypass annotations: {missing}"
        )
    if annotation["rule_id"] != "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001":
        raise RoundingDiscriminatorError("unexpected config-only bypass rule id")
    if annotation["claim_boundary"] != "LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE":
        raise RoundingDiscriminatorError("diagnostic must not claim a released baseline")
    return {"required_fields": list(required), "passed": True}


def _validate_replay_contract(contract: dict[str, Any]) -> dict[str, Any]:
    replay = contract["replay_contract"]
    if replay["rule_id"] != "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001":
        raise RoundingDiscriminatorError("unexpected replay rule id")
    if replay["classification"] != "formal_producer_output_delivery_not_host_precompute":
        raise RoundingDiscriminatorError("scratch must be a formal producer output")
    forbidden = (
        "host_precomputed_scaled_tensor",
        "host_precomputed_rounded_tensor",
        "host_precomputed_saturated_tensor",
        "host_precomputed_final_output",
    )
    if any(replay[key] is not False for key in forbidden):
        raise RoundingDiscriminatorError("host precomputation crossed the operator boundary")
    tensor = replay["tensor_identity"]
    if (
        tensor["dtype"] != "float32"
        or tensor["shape"] != [1, 1, 32]
        or tensor["bytes"] != 128
    ):
        raise RoundingDiscriminatorError("scratch replay tensor identity changed")
    return {
        "classification": replay["classification"],
        "source_producer": replay["source_producer"],
        "consumer": replay["consumer"],
        "host_precompute": False,
        "passed": True,
    }


def _constant_bits(config: dict[str, Any], pe_name: str, inport: str) -> int:
    value = config["general_array"]["PE_array"][pe_name][inport]["constant"]
    return _f32_bits(value)


def _assert_all_equal(values: list[Any], expected: Any, label: str) -> None:
    if not values or any(value != expected for value in values):
        raise RoundingDiscriminatorError(
            f"{label} mismatch: expected={expected!r} values={values!r}"
        )


def _validate_materialized_configs(
    stage0: dict[str, Any],
    stage1: dict[str, Any],
    negative: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    vector = contract["discriminator"]
    value = np.float32(vector["input_int32"])
    zero_point = int(vector["zero_point"])

    _assert_all_equal(
        [
            stage0["general_array"]["PE_array"][name]["alu_opcode"]
            for name in EVEN_PES
        ],
        "mul",
        "stage0 opcodes",
    )
    if set(stage0["general_array"]["PE_array"]) != set(EVEN_PES):
        raise RoundingDiscriminatorError("stage0 must contain only even-column MUL PEs")
    _assert_all_equal(
        [_constant_bits(stage0, name, "inport1") for name in EVEN_PES],
        DISCRIMINATOR_MULTIPLIER_BITS,
        "stage0 multiplier bits",
    )
    if (
        stage0["general_array"]["inport"]["inport0"]["int32tofp32"] != "true"
        or stage0["general_array"]["outport"]["int32touint8"] != "false"
    ):
        raise RoundingDiscriminatorError("stage0 conversion boundary changed")

    _assert_all_equal(
        [
            stage1["general_array"]["PE_array"][name]["alu_opcode"]
            for name in EVEN_PES
        ],
        "mac",
        "stage1 MAC opcodes",
    )
    _assert_all_equal(
        [_constant_bits(stage1, name, "inport1") for name in EVEN_PES],
        0x3F800000,
        "stage1 exact multiplier-one bits",
    )
    _assert_all_equal(
        [_constant_bits(stage1, name, "inport2") for name in EVEN_PES],
        MAGIC_BITS,
        "stage1 magic bits",
    )
    _assert_all_equal(
        [
            stage1["general_array"]["PE_array"][name]["inport1"]["constant"]
            for name in ODD_PES
        ],
        (MAGIC_BITS - zero_point) & 0xFFFFFFFF,
        "stage1 subtract constants",
    )
    if (
        stage1["general_array"]["inport"]["inport0"]["int32tofp32"] != "false"
        or stage1["general_array"]["outport"]["int32touint8"] != "true"
    ):
        raise RoundingDiscriminatorError("stage1 raw-FP32 or saturation boundary changed")

    _assert_all_equal(
        [_constant_bits(negative, name, "inport1") for name in EVEN_PES],
        DISCRIMINATOR_MULTIPLIER_BITS,
        "negative-control multiplier bits",
    )
    if negative["general_array"]["inport"]["inport0"]["int32tofp32"] != "true":
        raise RoundingDiscriminatorError("negative control must use INT32 ingress")

    if stage0["stream_engine"]["stream2"]["base_addr"] != "0x800000":
        raise RoundingDiscriminatorError("stage0 scratch write address changed")
    if stage1["stream_engine"]["stream0"]["base_addr"] != "0x800000":
        raise RoundingDiscriminatorError("stage1 scratch read address changed")

    scratch = np.float32(value * DISCRIMINATOR_MULTIPLIER)
    scratch_bits = f"0x{_f32_bits(scratch):08x}"
    if scratch_bits != vector["expected_stage0_scratch_bits"]:
        raise RoundingDiscriminatorError(
            f"stage0 scratch bits changed: {scratch_bits}"
        )
    staged_result = proposed_subtract_patch(float(scratch), zero_point)
    fused_result = one_round_fused_magic(
        value, DISCRIMINATOR_MULTIPLIER, zero_point
    )
    sequential = sequential_multiplier_tail(
        value, DISCRIMINATOR_MULTIPLIER, zero_point
    )
    expected = int(vector["expected_sequential_uint8"])
    expected_negative = int(vector["expected_fused_uint8"])
    if staged_result != expected or sequential != expected:
        raise RoundingDiscriminatorError(
            f"staged result changed: staged={staged_result} sequential={sequential}"
        )
    if fused_result != expected_negative:
        raise RoundingDiscriminatorError(
            f"negative-control result changed: fused={fused_result}"
        )
    if staged_result == fused_result:
        raise RoundingDiscriminatorError("26-vs-25 discriminator collapsed")

    return {
        "input_int32": int(value),
        "multiplier_bits": f"0x{DISCRIMINATOR_MULTIPLIER_BITS:08x}",
        "stage0_scratch_fp32_bits": scratch_bits,
        "staged_config_result_uint8": staged_result,
        "sequential_w3_result_uint8": sequential,
        "fused_negative_control_result_uint8": fused_result,
        "separation": staged_result - fused_result,
        "passed": True,
    }


def _validate_node0074_break(contract: dict[str, Any]) -> dict[str, Any]:
    item = contract["node0074_first_unavoidable_break"]
    if item["capability"] != "exact_binary32_division":
        raise RoundingDiscriminatorError("node0074 first break must remain exact division")
    x = np.asarray(int(item["minimal_counterexample"]["x_bits"], 16), dtype=np.uint32).view(
        np.float32
    )
    scale = np.asarray(
        int(item["minimal_counterexample"]["scale_bits"], 16), dtype=np.uint32
    ).view(np.float32)
    reciprocal = np.asarray(
        int(item["minimal_counterexample"]["reciprocal_bits"], 16), dtype=np.uint32
    ).view(np.float32)
    expected = max(0, min(255, int(np.rint(np.float32(x / scale)))))
    reciprocal_fused = one_round_fused_magic(x, reciprocal, 0)
    if expected != 2 or reciprocal_fused != 1:
        raise RoundingDiscriminatorError(
            "node0074 exact-division counterexample changed"
        )
    if item["target_json_generated"] is not False:
        raise RoundingDiscriminatorError("node0074 target generation is forbidden")
    return {
        "x_bits": item["minimal_counterexample"]["x_bits"],
        "scale_bits": item["minimal_counterexample"]["scale_bits"],
        "divide_then_rne_uint8": expected,
        "reciprocal_fma_magic_uint8": reciprocal_fused,
        "first_unavoidable_break": item["capability"],
        "passed": True,
    }


def _validate_flatten_endpoint_dependency(contract: dict[str, Any]) -> dict[str, Any]:
    dependency = contract["node0074_flatten_endpoint_dependency"]
    if (
        dependency["producer_node"] != 73
        or dependency["consumer_node"] != 74
        or dependency["consumer_port"] != "A"
    ):
        raise RoundingDiscriminatorError("unexpected Flatten-to-node0074 endpoint")
    if dependency["blocked_by"] != "B_QUANT_NODE0074_EXACT_DIVISION":
        raise RoundingDiscriminatorError(
            "Flatten endpoint dependency must remain behind exact division"
        )
    coverage = dependency["required_final_interface"]["read_coverage"]
    if (
        coverage["element_count"] != 32768
        or coverage["dtype"] != "float32"
        or coverage["required_bytes"] != 131072
    ):
        raise RoundingDiscriminatorError("Flatten endpoint coverage contract changed")
    unresolved_fields = (
        "final_storage_identity",
        "final_producer_base",
        "final_view_offset",
        "final_consumer_base",
        "final_read_coverage",
        "final_accepted_lifetime",
    )
    if any(dependency[field] is not None for field in unresolved_fields):
        raise RoundingDiscriminatorError(
            "provisional Flatten endpoint values must not be materialized"
        )
    if (
        dependency["provisional_address_allowed"] is not False
        or dependency["dependency_only"] is not True
        or dependency["target_endpoint_claimed"] is not False
    ):
        raise RoundingDiscriminatorError("Flatten endpoint claim boundary changed")
    return {
        "status": dependency["status"],
        "blocked_by": dependency["blocked_by"],
        "required_final_interface": dependency["required_final_interface"],
        "provisional_address_allowed": False,
        "target_endpoint_claimed": False,
        "passed": True,
    }


def build_bundle(
    contract_path: Path, project_root: Path, output_dir: Path
) -> dict[str, Any]:
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise RoundingDiscriminatorError(
            f"unexpected contract schema: {contract.get('schema')}"
        )
    oracle_path = project_root / contract["configuration_oracle"]["path"]
    oracle = _load_json(oracle_path)
    zero_point = int(contract["discriminator"]["zero_point"])
    configs = {
        CONFIG_FILENAMES[0]: _build_stage0(oracle),
        CONFIG_FILENAMES[1]: _build_stage1(oracle, zero_point),
        CONFIG_FILENAMES[2]: _build_negative_control(oracle, zero_point),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, config in configs.items():
        _write_json(output_dir / filename, config)

    ownership = _build_leaf_ownership(oracle, configs, contract)
    _write_json(output_dir / OWNERSHIP_FILENAME, ownership)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "LOCAL_CONFIG_BOUND_DIAGNOSTIC_MATERIALIZED",
        "candidate_release": False,
        "server_package": False,
        "target_json": False,
        "mapping": False,
        "bitstream": False,
        "execplan": False,
        "sca": False,
        "contract": {
            "path": contract_path.relative_to(project_root).as_posix(),
            "sha256": _sha256(contract_path),
        },
        "final_refresh_receipt": contract["final_refresh_receipt"],
        "configs": {
            filename: {"sha256": _sha256(output_dir / filename)}
            for filename in CONFIG_FILENAMES
        },
        "materialized_leaf_ownership": {
            "path": OWNERSHIP_FILENAME,
            "sha256": _sha256(output_dir / OWNERSHIP_FILENAME),
            "declaration_count": ownership["declaration_count"],
        },
        "bypass_annotation": contract["bypass_annotation"],
        "replay_contract": contract["replay_contract"],
        "transaction_contract": contract["transaction_contract"],
        "lifetime_contract": contract["lifetime_contract"],
        "node0074_target_generated": False,
        "node0074_flatten_endpoint_dependency": contract[
            "node0074_flatten_endpoint_dependency"
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def validate_bundle(
    contract_path: Path, project_root: Path, output_dir: Path
) -> dict[str, Any]:
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise RoundingDiscriminatorError(
            f"unexpected contract schema: {contract.get('schema')}"
        )
    if contract["candidate_release"] is not False:
        raise RoundingDiscriminatorError("diagnostic candidate_release must be false")
    if contract["forbidden_outputs"] != {
        "target_json": False,
        "mapping": False,
        "bitstream": False,
        "execplan": False,
        "sca": False,
        "server_package": False,
    }:
        raise RoundingDiscriminatorError("forbidden output boundary changed")

    manifest = _load_json(output_dir / "manifest.json")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise RoundingDiscriminatorError("unexpected manifest schema")
    if manifest["candidate_release"] is not False or manifest["server_package"] is not False:
        raise RoundingDiscriminatorError("manifest release boundary changed")
    if manifest["contract"]["sha256"] != _sha256(contract_path):
        raise RoundingDiscriminatorError("manifest contract identity changed")

    configs = {
        filename: _load_json(output_dir / filename) for filename in CONFIG_FILENAMES
    }
    for filename in CONFIG_FILENAMES:
        actual = _sha256(output_dir / filename)
        if manifest["configs"][filename]["sha256"] != actual:
            raise RoundingDiscriminatorError(
                f"materialized config identity changed: {filename}"
            )

    oracle = _load_json(project_root / contract["configuration_oracle"]["path"])
    expected_ownership = _build_leaf_ownership(oracle, configs, contract)
    actual_ownership = _load_json(output_dir / OWNERSHIP_FILENAME)
    if actual_ownership != expected_ownership:
        raise RoundingDiscriminatorError(
            "materialized leaf ownership contract does not match the final JSON leaf diff"
        )
    if (
        manifest["materialized_leaf_ownership"]["sha256"]
        != _sha256(output_dir / OWNERSHIP_FILENAME)
        or manifest["materialized_leaf_ownership"]["declaration_count"]
        != actual_ownership["declaration_count"]
    ):
        raise RoundingDiscriminatorError(
            "manifest materialized leaf ownership identity changed"
        )

    bypass = _validate_bypass_annotation(contract)
    replay = _validate_replay_contract(contract)
    semantic_sources = _validate_source_identities(project_root, contract)
    receipts = _validate_read_receipts(project_root, contract)
    final_refresh_receipts = _validate_read_receipts(
        project_root,
        contract,
        field="final_refresh_receipt",
        gate="final_validation_snapshot_provenance_only",
    )
    discriminator = _validate_materialized_configs(
        configs[CONFIG_FILENAMES[0]],
        configs[CONFIG_FILENAMES[1]],
        configs[CONFIG_FILENAMES[2]],
        contract,
    )
    node0074 = _validate_node0074_break(contract)
    flatten_dependency = _validate_flatten_endpoint_dependency(contract)
    coverage = [
        _materialized_output_coverage(CONFIG_FILENAMES[0], configs[CONFIG_FILENAMES[0]], 128),
        _materialized_output_coverage(CONFIG_FILENAMES[1], configs[CONFIG_FILENAMES[1]], 32),
        _materialized_output_coverage(CONFIG_FILENAMES[2], configs[CONFIG_FILENAMES[2]], 32),
    ]
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS_LOCAL_CONFIG_BOUND_26_VS_25_DIAGNOSTIC",
        "claim": "LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE",
        "candidate_release": False,
        "contract": {
            "path": contract_path.relative_to(project_root).as_posix(),
            "sha256": _sha256(contract_path),
        },
        "manifest": {
            "path": _display_path(output_dir / "manifest.json", project_root),
            "sha256": _sha256(output_dir / "manifest.json"),
        },
        "bypass_annotation": bypass,
        "replay_contract": replay,
        "materialized_leaf_ownership": {
            "path": _display_path(output_dir / OWNERSHIP_FILENAME, project_root),
            "sha256": _sha256(output_dir / OWNERSHIP_FILENAME),
            "declaration_count": actual_ownership["declaration_count"],
            "per_config_count": actual_ownership["per_config_count"],
            "all_final_leaf_diffs_owned": True,
        },
        "semantic_source_identity_count": len(semantic_sources),
        "semantic_source_identities": semantic_sources,
        "read_receipt_count": len(receipts),
        "read_receipts": receipts,
        "final_refresh_receipt_count": len(final_refresh_receipts),
        "final_refresh_receipts": final_refresh_receipts,
        "discriminator": discriminator,
        "node0074_first_unavoidable_break": node0074,
        "node0074_flatten_endpoint_dependency": flatten_dependency,
        "materialized_output_coverage": coverage,
        "transaction_contract": contract["transaction_contract"],
        "lifetime_contract": contract["lifetime_contract"],
        "generated_outputs": {
            "diagnostic_configs": 3,
            "target_json": False,
            "mapping": False,
            "bitstream": False,
            "execplan": False,
            "sca": False,
            "server_package": False,
        },
    }


def write_report(
    contract_path: Path, project_root: Path, output_dir: Path, report_path: Path
) -> dict[str, Any]:
    report = validate_bundle(contract_path, project_root, output_dir)
    _write_json(report_path, report)
    return report
