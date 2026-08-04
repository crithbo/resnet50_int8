from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_stage_ir import validate_deepseek_stage_ir
from .gap_sum_padding_contract import (
    validate_gap_sum_zero_padding_contract,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .strict_config_materialization import (
    validate_materialized_strict_config,
)


SCHEMA = "deepseek-reduction-to-resnet-gap-rule-evidence-v1"
STAGE_IR_PATH = (
    "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
)
HARDWARE_EVIDENCE_PATH = (
    "contracts/operator_config/ndpsim_json_hardware_evidence_v1.json"
)
GAP_CONTRACT_PATH = (
    "contracts/operator_config/gap_sum_zero_padding_contract_v1.json"
)
GAP_STRICT_ROOT = (
    "configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1"
)
GAP_HW_OP_ID = "hwop-0071-00"
GAP_REQUEST_ID = f"r5:{GAP_HW_OP_ID}"
RMSNORM_GRAPH = "ndp-sim/model_execplan/op_json/rmsnorm.json"
LOCAL_SUM_TYPES = (
    "decode_summac_fp32N_fp32N",
    "prefill_summac_fp16MN_fp32MN",
    "prefill_summac_fp32MN_fp32MN",
)
REMOTE_SUM_TYPES = (
    "decode_remote_sum_fp32N_fp32N",
    "prefill_remote_sum_fp32MN_fp32MN",
    "prefill_remote_sum_4slice_fp16MN_fp32MN",
    "prefill_remote_sum_4slice_fp32MN_fp32MN",
)
REDUCTION_TYPES = LOCAL_SUM_TYPES + REMOTE_SUM_TYPES


class DeepSeekReductionRuleError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekReductionRuleError(
            f"cannot parse reduction evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekReductionRuleError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekReductionRuleError(
            f"required reduction evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _validate_config(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    config = _load(path)
    report = OperatorConfigValidator().validate(
        config, source=str(path)
    ).to_dict()
    completion = report.get("facts", {}).get("completion")
    if (
        report.get("valid") is not True
        or report.get("facts", {}).get("issue_count") != 0
        or not isinstance(completion, Mapping)
        or 0 not in completion.get("possible_last_indices", [])
        or completion.get("write_target") != "D"
    ):
        raise DeepSeekReductionRuleError(
            f"reduction terminal/completion chain is not closed: {relative}"
        )
    return {
        "config": _binding(root, relative),
        "config_mask": config.get("CONFIG"),
        "completion": deepcopy(dict(completion)),
        "config_state": deepcopy(report["facts"]["config"]),
        "next_config_state": deepcopy(report["next_config_state"]),
    }


def _stage_records(
    stage_ir: Mapping[str, Any], stage_type: str
) -> list[dict[str, Any]]:
    return [
        deepcopy(dict(item))
        for item in stage_ir.get("stage_records", [])
        if isinstance(item, Mapping) and item.get("stage_type") == stage_type
    ]


def _ga_opcodes(config: Mapping[str, Any]) -> list[str]:
    pe_array = config.get("general_array", {}).get("PE_array", {})
    if not isinstance(pe_array, Mapping):
        return []
    return sorted(
        {
            str(value["alu_opcode"])
            for value in pe_array.values()
            if isinstance(value, Mapping)
            and isinstance(value.get("alu_opcode"), str)
        }
    )


def _loop_iterations(loop: Mapping[str, Any]) -> int:
    start = loop.get("start")
    end = loop.get("end")
    stride = loop.get("stride")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or isinstance(stride, bool)
        or not all(isinstance(value, int) for value in (start, end, stride))
        or stride <= 0
        or end < start
    ):
        raise DeepSeekReductionRuleError("GAP output loop is malformed")
    return (end - start + stride - 1) // stride


def build_deepseek_reduction_rules(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    stage_ir = _load(root / STAGE_IR_PATH)
    validate_deepseek_stage_ir(stage_ir, root)
    gap_contract = validate_gap_sum_zero_padding_contract(
        root, root / GAP_CONTRACT_PATH
    )
    gap_manifest = validate_materialized_strict_config(
        root / GAP_STRICT_ROOT
    )
    gap_path = root / GAP_STRICT_ROOT / "config.json"
    gap_config = _load(gap_path)
    gap_report = OperatorConfigValidator().validate(
        gap_config, source=str(gap_path)
    ).to_dict()
    if gap_report.get("valid") is not True:
        raise DeepSeekReductionRuleError("strict GAP config no longer validates")

    hardware = _load(root / HARDWARE_EVIDENCE_PATH)
    hardware_by_id = {
        str(item["template_id"]): item
        for item in hardware.get("records", [])
        if isinstance(item, Mapping)
    }
    decode_summac_evidence = hardware_by_id.get(
        "decode_summac_fp32N_fp32N"
    )
    if (
        not isinstance(decode_summac_evidence, Mapping)
        or decode_summac_evidence.get("positive_hardware_test_proven")
        is not True
        or decode_summac_evidence.get("exact_config_evidence", {}).get(
            "evidence_level"
        )
        != "E3-reported"
    ):
        raise DeepSeekReductionRuleError(
            "DeepSeek decode summac completion evidence differs"
        )

    reduction_templates: dict[str, Any] = {}
    for stage_type in REDUCTION_TYPES:
        relative = f"ndp-sim/jsons/{stage_type}.json"
        config = _load(root / relative)
        records = _stage_records(stage_ir, stage_type)
        crosswalk = stage_ir.get("template_crosswalk", {}).get(stage_type)
        if (
            not isinstance(crosswalk, Mapping)
            or crosswalk.get("configuration_authority", {}).get(
                "accepted_as_correct_reference"
            )
            is not True
            or crosswalk.get("template", {}).get("sha256")
            != sha256_file(root / relative)
        ):
            raise DeepSeekReductionRuleError(
                f"reduction template authority differs: {stage_type}"
            )
        reduction_templates[stage_type] = {
            "role": (
                "local_reduction"
                if stage_type in LOCAL_SUM_TYPES
                else "remote_reduction"
            ),
            "stage_occurrence_count": len(records),
            "stage_ids": sorted(item["stage_id"] for item in records),
            "graph_shapes": [
                {
                    "graph_path": item["graph_path"],
                    "operator_id": item["operator_id"],
                    "inputs": deepcopy(item["inputs"]),
                    "output": deepcopy(item["output"]),
                    "graph_used_slices": deepcopy(
                        item["graph_used_slices"]
                    ),
                    "stage_used_slices": deepcopy(
                        item["stage_used_slices"]
                    ),
                }
                for item in records
            ],
            "ga_opcodes": _ga_opcodes(config),
            "strict_terminal_evidence": _validate_config(root, relative),
        }

    rmsnorm = [
        item
        for item in stage_ir["stage_records"]
        if item["graph_path"] == RMSNORM_GRAPH
    ]
    rmsnorm.sort(key=lambda item: item["graph_location"])
    expected_rmsnorm = [
        "prefill_summac_fp32MN_fp32MN",
        "prefill_remote_sum_fp32MN_fp32MN",
        "prefill_mac_SFU_fp32MN_fp32MN",
        "prefill_mul_fp32MN_fp32M_fp32MN",
    ]
    if [item["stage_type"] for item in rmsnorm] != expected_rmsnorm:
        raise DeepSeekReductionRuleError("RMSNorm reduction stage DAG differs")
    remote_input = rmsnorm[1]["inputs"]
    if (
        len(remote_input) != 1
        or remote_input[0]["source_kind"] != "local_stage"
        or remote_input[0]["source"] != "op0"
    ):
        raise DeepSeekReductionRuleError(
            "RMSNorm local-to-remote reduction dependency differs"
        )

    semantics = gap_contract["operator_semantics"]
    if (
        semantics.get("request_id") != GAP_REQUEST_ID
        or semantics.get("input_shape") != [16, 2048, 7, 7]
        or semantics.get("output_shape") != [16, 2048, 1, 1]
        or semantics.get("input_zero_point") != 0
        or semantics.get("spatial_element_count") != 49
        or semantics.get("lane_count") != 8
    ):
        raise DeepSeekReductionRuleError("GAP typed semantics differ")
    loops = gap_config.get("dram_loop_configs")
    write_stream = gap_config.get("stream_engine", {}).get("stream1")
    pe_array = gap_config.get("general_array", {}).get("PE_array")
    if (
        not isinstance(loops, Mapping)
        or not isinstance(loops.get("LC0"), Mapping)
        or not isinstance(write_stream, Mapping)
        or write_stream.get("mode") != "write"
        or write_stream.get("target") != "D"
        or not isinstance(pe_array, Mapping)
    ):
        raise DeepSeekReductionRuleError("GAP schedule topology differs")
    outer_iterations = _loop_iterations(loops["LC0"])
    idx_size = write_stream.get("idx_size")
    if (
        outer_iterations != 256
        or not isinstance(idx_size, list)
        or idx_size[0] != 31
        or len(pe_array) != 8
        or _ga_opcodes(gap_config) != ["int32_sum"]
    ):
        raise DeepSeekReductionRuleError("GAP output coverage differs")
    output_bytes_per_sample = outer_iterations * (idx_size[0] + 1)
    expected_output_bytes = 2048 * 4
    if output_bytes_per_sample != expected_output_bytes:
        raise DeepSeekReductionRuleError(
            "GAP config does not emit one complete channel vector per invocation"
        )
    completion = gap_report.get("facts", {}).get("completion")
    if (
        not isinstance(completion, Mapping)
        or 0 not in completion.get("possible_last_indices", [])
        or completion.get("write_target") != "D"
    ):
        raise DeepSeekReductionRuleError("GAP terminal chain differs")

    gap_resolution = {
        "request_id": GAP_REQUEST_ID,
        "hw_op_id": GAP_HW_OP_ID,
        "exact_schedule": {
            "batch_count": 16,
            "channels_per_sample": 2048,
            "reduction_axes": [2, 3],
            "reduction_domain_per_output": 49,
            "samples_per_slice": 1,
            "active_slice_count": 16,
            "available_slice_count": gap_report["facts"]["target_profile"][
                "slices"
            ],
            "wave_active_slice_counts": [16],
            "input_bytes_per_slice": 2048 * 7 * 7,
            "output_bytes_per_slice": output_bytes_per_sample,
            "output_channels_covered_per_slice": (
                output_bytes_per_sample // 4
            ),
        },
        "cross_slice_classification": {
            "required": False,
            "reason": (
                "the reduction axes are spatial only; one slice receives one "
                "complete batch sample and the exact config emits all 2048 "
                "channel sums, so no output element has a reduction domain "
                "split across slices"
            ),
            "deepseek_remote_sum_rule": (
                "remote reduction is selected only when a preceding local "
                "stage partitions one reduction domain across slices, as in "
                "the hash-bound RMSNorm op0->op1 stage DAG"
            ),
        },
        "typed_parameter_consumption": {
            "parameter": "x_zero_point",
            "value": 0,
            "mode": "compile_time_specialization",
            "specialization": (
                "sum(uint8(x)-0) becomes plain uint8-to-int32 sum; zero also "
                "binds the padding additive identity"
            ),
            "runtime_parameter_transport_required": False,
        },
        "completion": {
            "strict_validator": deepcopy(dict(completion)),
            "authorized_exact_template": True,
            "local_config_completion_resolved": True,
            "server_execution_claim": False,
        },
        "resolved_local_blockers": [
            "B_EXECPLAN_TYPED_TRANSPORT",
            "B_SUM_COMPLETION",
            "B_SUM_CROSS_SLICE",
        ],
        "remaining_release_gates": [
            "B_ADDRESS_MAPPING_EXECPLAN_SCA",
            "B_SERVER_E4_E5",
        ],
    }

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "deepseek_reduction_rules_extracted_exact_gap_local_schedule_closed"
        ),
        "inputs": {
            "deepseek_stage_ir": _binding(root, STAGE_IR_PATH),
            "hardware_evidence": _binding(
                root, HARDWARE_EVIDENCE_PATH
            ),
            "gap_padding_and_numeric_contract": _binding(
                root, GAP_CONTRACT_PATH
            ),
            "gap_strict_materialization": _binding(
                root, f"{GAP_STRICT_ROOT}/manifest.json"
            ),
            "gap_strict_config": _binding(
                root, f"{GAP_STRICT_ROOT}/config.json"
            ),
        },
        "policy": {
            "deepseek_exact_configs_are_authorized_reference_semantics": True,
            "local_and_remote_reduction_are_distinguished_by_partitioned_axis": True,
            "terminal_static_closure_is_not_server_e4_e5": True,
            "zero_typed_parameter_may_be_compile_time_specialized": True,
            "address_binding_mapping_execplan_and_sca_remain_separate": True,
        },
        "deepseek_reduction_stage_dag": {
            "graph": _binding(root, RMSNORM_GRAPH),
            "stage_types": expected_rmsnorm,
            "local_to_remote_dependency": "op0->op1",
            "rule": (
                "insert remote reduction only when the local output preserves "
                "a slice-partitioned reduction axis"
            ),
        },
        "reference_reduction_templates": reduction_templates,
        "gap_resolution": gap_resolution,
    }
    payload["evidence_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_deepseek_reduction_rules(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_reduction_rules(project_root):
        raise DeepSeekReductionRuleError(
            "DeepSeek reduction rule evidence differs from current inputs"
        )


def write_deepseek_reduction_rules(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "SCHEMA",
    "DeepSeekReductionRuleError",
    "build_deepseek_reduction_rules",
    "validate_deepseek_reduction_rules",
    "write_deepseek_reduction_rules",
]
