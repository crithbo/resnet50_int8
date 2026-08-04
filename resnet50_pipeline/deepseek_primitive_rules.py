from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_stage_ir import validate_deepseek_stage_ir
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import (
    CONTROL_REGISTERS_PATH,
    JSON_LOADER_PATH,
    OUTPUT_WRITER_PATH,
    PIPELINE_PATH,
    native_control_handlers,
)
from .operator_config_validator import OperatorConfigValidator


SCHEMA = "deepseek-ga-sa-n2n-primitive-rule-evidence-v1"
STAGE_IR_PATH = (
    "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
)
GA_OPERATIONS = ("add", "mul", "mac")
SA_TYPES = (
    "decode_gemv_local",
    "decode_gemv_ring",
    "gemv_config_local_M1N128K32",
    "prefill_gemm_local",
    "prefill_gemm_local_qkt",
    "prefill_gemm_ring_4slice",
)
LOCAL_RING_PAIRS = (
    ("decode_gemv_local", "decode_gemv_ring"),
    ("prefill_gemm_local", "prefill_gemm_ring_4slice"),
)


class DeepSeekPrimitiveRuleError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekPrimitiveRuleError(
            f"cannot parse primitive evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekPrimitiveRuleError(
            f"primitive JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekPrimitiveRuleError(
            f"required primitive evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _stage_records(
    stage_ir: Mapping[str, Any], stage_type: str
) -> list[Mapping[str, Any]]:
    return [
        item
        for item in stage_ir.get("stage_records", [])
        if isinstance(item, Mapping) and item.get("stage_type") == stage_type
    ]


def _authorized_template(
    root: Path, stage_ir: Mapping[str, Any], stage_type: str
) -> tuple[str, dict[str, Any], Mapping[str, Any]]:
    crosswalk = stage_ir.get("template_crosswalk", {}).get(stage_type)
    if not isinstance(crosswalk, Mapping):
        raise DeepSeekPrimitiveRuleError(
            f"missing DeepSeek template crosswalk: {stage_type}"
        )
    authority = crosswalk.get("configuration_authority")
    template = crosswalk.get("template")
    if (
        not isinstance(authority, Mapping)
        or authority.get("accepted_as_correct_reference") is not True
        or authority.get("provenance", {}).get("kind")
        != "pinned_upstream_exact_blob"
        or not isinstance(template, Mapping)
    ):
        raise DeepSeekPrimitiveRuleError(
            f"template is not an authorized upstream baseline: {stage_type}"
        )
    relative = str(template.get("path"))
    config = _load(root / relative)
    if template.get("sha256") != sha256_file(root / relative):
        raise DeepSeekPrimitiveRuleError(
            f"template identity differs: {stage_type}"
        )
    return relative, config, crosswalk


def _validation_facts(config: Mapping[str, Any], source: str) -> dict[str, Any]:
    report = OperatorConfigValidator().validate(
        config, source=source
    ).to_dict()
    completion = report.get("facts", {}).get("completion")
    if (
        not isinstance(completion, Mapping)
        or 0 not in completion.get("possible_last_indices", [])
        or completion.get("write_target") != "D"
    ):
        raise DeepSeekPrimitiveRuleError(
            f"primitive terminal chain failed: {source}"
        )
    return {
        "strict_validator_compatible": report.get("valid") is True,
        "issue_count": report.get("facts", {}).get("issue_count"),
        "issues": deepcopy(report.get("issues", [])),
        "config_mask": config.get("CONFIG"),
        "config_state": deepcopy(report["facts"]["config"]),
        "next_config_state": deepcopy(report["next_config_state"]),
        "completion": deepcopy(dict(completion)),
        "stream_facts": deepcopy(report["facts"]["streams"]),
        "sa_layout": deepcopy(report["facts"].get("sa_layout")),
    }


def _operation(stage_type: str) -> str | None:
    for operation in GA_OPERATIONS:
        if f"_{operation}_" in stage_type:
            return operation
    return None


def _unique(values: list[Any]) -> list[Any]:
    by_key = {canonical_json_bytes(value): deepcopy(value) for value in values}
    return [by_key[key] for key in sorted(by_key)]


def _ga_facts(config: Mapping[str, Any]) -> dict[str, Any]:
    ga = config.get("general_array")
    pe_array = ga.get("PE_array") if isinstance(ga, Mapping) else None
    if not isinstance(ga, Mapping) or not isinstance(pe_array, Mapping):
        raise DeepSeekPrimitiveRuleError("GA primitive has no PE_array")
    lanes = [
        (str(name), value)
        for name, value in sorted(pe_array.items())
        if isinstance(value, Mapping)
    ]
    if not lanes:
        raise DeepSeekPrimitiveRuleError("GA primitive has no active lanes")
    input_modes: dict[str, list[Any]] = {}
    input_constants: dict[str, list[Any]] = {}
    for port in ("inport0", "inport1", "inport2"):
        input_modes[port] = _unique(
            [
                lane.get(port, {}).get("mode")
                for _, lane in lanes
                if isinstance(lane.get(port), Mapping)
            ]
        )
        input_constants[port] = _unique(
            [
                lane.get(port, {}).get("constant")
                for _, lane in lanes
                if isinstance(lane.get(port), Mapping)
            ]
        )
    return {
        "active_lane_names": [name for name, _ in lanes],
        "active_lane_count": len(lanes),
        "alu_opcodes": _unique(
            [lane.get("alu_opcode") for _, lane in lanes]
        ),
        "transout_last_indices": _unique(
            [lane.get("transout_last_index") for _, lane in lanes]
        ),
        "lane_input_modes": input_modes,
        "lane_input_constants": input_constants,
        "global_inports": deepcopy(ga.get("inport")),
        "global_outport": deepcopy(ga.get("outport")),
    }


def _occurrences(
    stage_ir: Mapping[str, Any], stage_type: str
) -> list[dict[str, Any]]:
    return [
        {
            "stage_id": item["stage_id"],
            "graph_path": item["graph_path"],
            "operator_id": item["operator_id"],
            "graph_used_slices": deepcopy(item["graph_used_slices"]),
            "stage_used_slices": deepcopy(item["stage_used_slices"]),
            "inputs": deepcopy(item["inputs"]),
            "output": deepcopy(item["output"]),
        }
        for item in _stage_records(stage_ir, stage_type)
    ]


def _sa_facts(config: Mapping[str, Any]) -> dict[str, Any]:
    sa = config.get("special_array")
    if not isinstance(sa, Mapping):
        raise DeepSeekPrimitiveRuleError("SA primitive has no special_array")
    shape = config.get("gemm_shape", config.get("gemv_shape"))
    if not isinstance(shape, Mapping):
        raise DeepSeekPrimitiveRuleError("SA primitive has no GEMM/GEMV shape")
    neighbor_ports = [
        port
        for port in ("inport0", "inport1", "inport2")
        if isinstance(sa.get(port), Mapping)
        and sa[port].get("nbr_enable") == 1
    ]
    ga = config.get("general_array")
    ga_opcodes: list[Any] = []
    if isinstance(ga, Mapping) and isinstance(ga.get("PE_array"), Mapping):
        ga_opcodes = _unique(
            [
                value.get("alu_opcode")
                for value in ga["PE_array"].values()
                if isinstance(value, Mapping)
            ]
        )
    return {
        "shape": deepcopy(dict(shape)),
        "special_array": deepcopy(dict(sa)),
        "n2n": deepcopy(config.get("n2n")),
        "neighbor_enabled_inports": neighbor_ports,
        "post_sa_ga_opcodes": ga_opcodes,
    }


def _pair_evidence(
    records: Mapping[str, Mapping[str, Any]],
    local_type: str,
    ring_type: str,
) -> dict[str, Any]:
    local = records[local_type]
    ring = records[ring_type]
    stable_fields = (
        "mode",
        "bias_enable",
        "data_type",
        "transout_last_index",
        "outport",
    )
    local_sa = local["sa_facts"]["special_array"]
    ring_sa = ring["sa_facts"]["special_array"]
    stable = {
        field: {
            "local": deepcopy(local_sa.get(field)),
            "ring": deepcopy(ring_sa.get(field)),
            "equal": local_sa.get(field) == ring_sa.get(field),
        }
        for field in stable_fields
    }
    if not all(item["equal"] for item in stable.values()):
        raise DeepSeekPrimitiveRuleError(
            f"local/ring SA stable fields differ: {local_type}/{ring_type}"
        )
    if (
        local["sa_facts"]["n2n"] is not None
        or ring["sa_facts"]["n2n"] is None
        or local["sa_facts"]["neighbor_enabled_inports"]
        or not ring["sa_facts"]["neighbor_enabled_inports"]
    ):
        raise DeepSeekPrimitiveRuleError(
            f"local/ring neighbor topology differs: {local_type}/{ring_type}"
        )
    return {
        "local_type": local_type,
        "ring_type": ring_type,
        "equal_config_mask": (
            local["validation"]["config_mask"]
            == ring["validation"]["config_mask"]
        ),
        "stable_sa_fields": stable,
        "local_shape": deepcopy(local["sa_facts"]["shape"]),
        "ring_shape": deepcopy(ring["sa_facts"]["shape"]),
        "ring_adds_n2n": True,
        "ring_neighbor_enabled_inports": deepcopy(
            ring["sa_facts"]["neighbor_enabled_inports"]
        ),
        "rule": (
            "ring selection changes the K partition, loop/stream schedule and "
            "neighbor topology together; adding n2n to a local template is "
            "not a valid derivation"
        ),
    }


def build_deepseek_primitive_rules(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    stage_ir = _load(root / STAGE_IR_PATH)
    validate_deepseek_stage_ir(stage_ir, root)
    native_handlers = native_control_handlers(root)
    stage_types = sorted(stage_ir.get("template_crosswalk", {}))
    ga_types = [
        stage_type
        for stage_type in stage_types
        if _operation(stage_type) is not None
        and "summac" not in stage_type
        and "mac_SFU" not in stage_type
    ]
    if len(ga_types) != 22:
        raise DeepSeekPrimitiveRuleError(
            f"GA elementwise inventory differs: {len(ga_types)}"
        )

    ga_records: dict[str, Any] = {}
    for stage_type in ga_types:
        relative, config, crosswalk = _authorized_template(
            root, stage_ir, stage_type
        )
        operation = _operation(stage_type)
        handler_name = native_handlers.get(stage_type)
        if not handler_name:
            raise DeepSeekPrimitiveRuleError(
                f"native model_execplan handler is missing: {stage_type}"
            )
        ga_facts = _ga_facts(config)
        if ga_facts["alu_opcodes"] != [operation]:
            raise DeepSeekPrimitiveRuleError(
                f"GA opcode/type mismatch: {stage_type}"
            )
        ga_records[stage_type] = {
            "operation": operation,
            "native_control_handler": handler_name,
            "template": _binding(root, relative),
            "authority": deepcopy(crosswalk["configuration_authority"]),
            "ga_facts": ga_facts,
            "validation": _validation_facts(config, relative),
            "occurrences": _occurrences(stage_ir, stage_type),
        }

    sa_records: dict[str, Any] = {}
    for stage_type in SA_TYPES:
        relative, config, crosswalk = _authorized_template(
            root, stage_ir, stage_type
        )
        facts = _sa_facts(config)
        handler_name = native_handlers.get(stage_type)
        if stage_type != "gemv_config_local_M1N128K32" and not handler_name:
            raise DeepSeekPrimitiveRuleError(
                f"native model_execplan handler is missing: {stage_type}"
            )
        is_ring = "ring" in stage_type
        if is_ring != (facts["n2n"] is not None):
            raise DeepSeekPrimitiveRuleError(
                f"SA ring/N2N classification differs: {stage_type}"
            )
        if is_ring != bool(facts["neighbor_enabled_inports"]):
            raise DeepSeekPrimitiveRuleError(
                f"SA ring/neighbor-port classification differs: {stage_type}"
            )
        sa_records[stage_type] = {
            "role": "ring_partition" if is_ring else "local_partition",
            "native_control_handler": handler_name,
            "template": _binding(root, relative),
            "authority": deepcopy(crosswalk["configuration_authority"]),
            "sa_facts": facts,
            "validation": _validation_facts(config, relative),
            "occurrences": _occurrences(stage_ir, stage_type),
        }

    pairs = [
        _pair_evidence(sa_records, local_type, ring_type)
        for local_type, ring_type in LOCAL_RING_PAIRS
    ]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "native_ndpsim_ga_sa_n2n_capabilities_audited_"
            "no_parallel_generator"
        ),
        "inputs": {
            "deepseek_stage_ir": _binding(root, STAGE_IR_PATH),
            "native_graph_parser": _binding(root, JSON_LOADER_PATH),
            "native_control_registers": _binding(
                root, CONTROL_REGISTERS_PATH
            ),
            "native_json_patcher": _binding(root, OUTPUT_WRITER_PATH),
            "native_execution_pipeline": _binding(root, PIPELINE_PATH),
        },
        "summary": {
            "ga_elementwise_template_count": len(ga_records),
            "ga_elementwise_stage_occurrence_count": sum(
                len(item["occurrences"]) for item in ga_records.values()
            ),
            "sa_template_count": len(sa_records),
            "sa_stage_occurrence_count": sum(
                len(item["occurrences"]) for item in sa_records.values()
            ),
            "ring_template_count": sum(
                item["role"] == "ring_partition"
                for item in sa_records.values()
            ),
            "local_ring_pair_count": len(pairs),
            "native_control_handler_count": len(native_handlers),
            "graph_referenced_stage_type_native_handler_count": len(
                {
                    item["stage_type"]
                    for item in stage_ir["stage_records"]
                    if item["stage_type"] in native_handlers
                }
            ),
            "strict_validator_incompatible_template_count": sum(
                not item["validation"]["strict_validator_compatible"]
                for item in [*ga_records.values(), *sa_records.values()]
            ),
        },
        "ga_elementwise": ga_records,
        "sa_matmul": sa_records,
        "local_ring_pairs": pairs,
        "transfer_policy": {
            "execution_owner": (
                "active ndp-sim model_execplan owns graph parsing, "
                "shape-driven control-register updates, JSON patching, "
                "address planning, bitstream and execution-plan generation"
            ),
            "project_layer_role": (
                "this contract is an audit/provenance and ResNet transfer-"
                "boundary layer; it is not a second operator generator"
            ),
            "exact_replay": (
                "an authorized template may be replayed only for its exact "
                "stage type, graph parameterization and dtype/shape contract"
            ),
            "structurally_reusable": [
                "GA opcode and active-lane topology",
                "graph-declared broadcast/source dependency",
                "CONFIG state ownership and terminal-tag chain",
                "SA local-versus-ring selection rule",
                "N2N and SA neighbor-port coupling",
            ],
            "not_proven_for_resnet_int8": [
                "INT8 Conv SA data type, asymmetric A/B layout and accumulation",
                "bias or partial-sum numeric placement",
                "quantization zero-points, multiplier, rounding and saturation",
                "ResNet-specific loop bounds, stream lengths and addresses",
            ],
            "psum_language_limit": (
                "the upstream JSON proves neighbor transport topology through "
                "n2n and nbr_enable; it contains no psum-labelled semantic "
                "field, so partial-sum arithmetic remains a separate blocker"
            ),
            "derived_template_requires_independent_validation": True,
            "strict_validator_compatibility": (
                "an authorized upstream exact template may contain inert "
                "fields that the strict target schema rejects; that status is "
                "recorded and never silently normalized"
            ),
        },
    }
    payload["evidence_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_deepseek_primitive_rules(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_primitive_rules(project_root):
        raise DeepSeekPrimitiveRuleError(
            "DeepSeek primitive evidence differs from current inputs"
        )


def write_deepseek_primitive_rules(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "SCHEMA",
    "DeepSeekPrimitiveRuleError",
    "build_deepseek_primitive_rules",
    "validate_deepseek_primitive_rules",
    "write_deepseek_primitive_rules",
]
