from __future__ import annotations

import ast
import json
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .hashing import sha256_file
from .target_config_audit import (
    TargetConfigAuditError,
    _run_encoder,
    _validate_ga_template,
)


SUM_TEMPLATE_NAMES = (
    "decode_remote_sum_fp32N_fp32N.json",
    "decode_sum_rec_fp32N_fp32N.json",
    "decode_summac_fp16N_fp32N.json",
    "decode_summac_fp32N_fp32N.json",
    "prefill_remote_sum_4slice_fp16MN_fp32MN.json",
    "prefill_remote_sum_4slice_fp32MN_fp32MN.json",
    "prefill_remote_sum_fp32MN_fp32MN.json",
    "prefill_sum_rec_fp32MN_fp32MN.json",
    "prefill_summac_fp16MN_fp32MN.json",
    "prefill_summac_fp32MN_fp32MN.json",
    "sum_config_32_32.json",
)

_HANDLERS = {
    "decode_remote_sum_fp32N_fp32N.json":
        "_compute_decode_remote_sum_fp32N_fp32N_control_register_updates",
    "decode_sum_rec_fp32N_fp32N.json":
        "_compute_decode_sum_rec_fp32N_fp32N_control_register_updates",
    "decode_summac_fp16N_fp32N.json":
        "_compute_decode_summac_fp16N_fp32N_control_register_updates",
    "decode_summac_fp32N_fp32N.json":
        "_compute_decode_summac_fp32N_fp32N_control_register_updates",
    "prefill_remote_sum_4slice_fp16MN_fp32MN.json":
        "_compute_prefill_remote_sum_4slice_fp16MN_fp32MN_control_register_updates",
    "prefill_remote_sum_4slice_fp32MN_fp32MN.json":
        "_compute_prefill_remote_sum_4slice_fp32MN_fp32MN_control_register_updates",
    "prefill_remote_sum_fp32MN_fp32MN.json":
        "_compute_prefill_remote_sum_fp32MN_fp32MN_control_register_updates",
    "prefill_sum_rec_fp32MN_fp32MN.json":
        "_compute_prefill_sum_rec_fp32MN_fp32MN_control_register_updates",
    "prefill_summac_fp16MN_fp32MN.json":
        "_compute_prefill_summac_fp16MN_fp32MN_control_register_updates",
    "prefill_summac_fp32MN_fp32MN.json":
        "_compute_prefill_summac_fp32MN_fp32MN_control_register_updates",
}


class SumConfigAuditError(RuntimeError):
    pass


def _family(template_name: str) -> str:
    if template_name == "sum_config_32_32.json":
        return "local_sum"
    if "summac" in template_name:
        return "summac"
    if "sum_rec" in template_name:
        return "sum_rec"
    if "remote_sum" in template_name:
        return "remote_sum"
    raise SumConfigAuditError(f"unsupported sum template: {template_name}")


def _expected_opcode_counts(template_name: str) -> Counter[str]:
    family = _family(template_name)
    lanes = 1 if template_name.startswith("decode_") else 8
    if family in {"local_sum", "remote_sum"}:
        if "fp16" in template_name:
            return Counter({"mul": lanes, "sum": lanes})
        return Counter({"sum": lanes})
    if family == "summac":
        return Counter({"mul": lanes, "summac": lanes})
    return Counter({"sum": lanes, "rec": lanes})


def _enabled_flags(record: dict[str, Any], fields: Iterable[str]) -> list[str]:
    return sorted(field for field in fields if record.get(field) in (True, "true"))


def _source_pe(port: dict[str, Any]) -> str | None:
    source = port.get("src_id")
    if isinstance(source, str) and source.startswith("GA_PE."):
        return source.removeprefix("GA_PE.")
    return None


def _validate_topology(config: dict[str, Any], template_name: str) -> None:
    ga = config["general_array"]
    pes = ga["PE_array"]
    family = _family(template_name)
    opcode_counts = Counter(pe["alu_opcode"] for pe in pes.values())
    expected = _expected_opcode_counts(template_name)
    if opcode_counts != expected:
        raise SumConfigAuditError(
            f"{template_name} GA opcode counts differ: actual={dict(opcode_counts)}, "
            f"expected={dict(expected)}"
        )

    if list(config["stream_engine"]) != ["stream0", "stream1"]:
        raise SumConfigAuditError(f"{template_name} must use exactly stream0 and stream1")
    read_stream = config["stream_engine"]["stream0"]
    write_stream = config["stream_engine"]["stream1"]
    if (read_stream["mode"], read_stream["target"]) != ("read", "A"):
        raise SumConfigAuditError(f"{template_name} stream0 must read A")
    if (write_stream["mode"], write_stream["target"]) != ("write", "D"):
        raise SumConfigAuditError(f"{template_name} stream1 must write D")

    conversion_fields = (
        "fp16tofp32",
        "bf16tofp32",
        "int32tofp32",
        "uint8tofp32",
        "uint8toint32",
    )
    expected_input_conversions = ["fp16tofp32"] if "fp16" in template_name else []
    for name, inport in ga["inport"].items():
        actual = _enabled_flags(inport, conversion_fields)
        expected_flags = expected_input_conversions if name == "inport0" else []
        if actual != expected_flags:
            raise SumConfigAuditError(
                f"{template_name} {name} conversions={actual}, expected={expected_flags}"
            )
        if inport["nbr_enable"] != 0:
            raise SumConfigAuditError(f"{template_name} unexpectedly enables GA neighbor input")
    output_conversions = _enabled_flags(
        ga["outport"], ("fp32tofp16", "fp32tobf16", "int32touint8")
    )
    if output_conversions:
        raise SumConfigAuditError(
            f"{template_name} unexpectedly converts output via {output_conversions}"
        )
    for name, buffer in config["buffer_config"].items():
        if buffer["nbr_enable"] != 0:
            raise SumConfigAuditError(f"{template_name} {name} unexpectedly enables neighbor flow")

    reduction_ops = {"sum", "summac"}
    for name, pe in pes.items():
        opcode = pe["alu_opcode"]
        if opcode in reduction_ops and pe["transout_last_index"] != 1:
            raise SumConfigAuditError(
                f"{template_name} {name} reduction must emit on last_index 1"
            )
        if opcode in {"mul", "rec"} and pe["transout_last_index"] is not None:
            raise SumConfigAuditError(
                f"{template_name} {name} non-reduction transout must be null"
            )

    if family == "summac":
        for name, pe in pes.items():
            if pe["alu_opcode"] != "summac":
                continue
            left = _source_pe(pe["inport0"])
            right = _source_pe(pe["inport1"])
            if left is None or left != right or pes.get(left, {}).get("alu_opcode") != "mul":
                raise SumConfigAuditError(
                    f"{template_name} {name} must square one mul result before summac"
                )
    if family == "sum_rec":
        for name, pe in pes.items():
            if pe["alu_opcode"] != "rec":
                continue
            source = _source_pe(pe["inport0"])
            if source is None or pes.get(source, {}).get("alu_opcode") != "sum":
                raise SumConfigAuditError(
                    f"{template_name} {name} must consume a sum PE"
                )

    completion = {
        "read_stream_full": read_stream["buf_full_last_index"],
        "input_buffer_full": config["buffer_config"]["buffer0"]["buf_full_last_index"],
        "input_row": config["buffer_loop_configs"]["GROUP0"]["ROW_LC"]["last_index"],
        "input_col": config["buffer_loop_configs"]["GROUP0"]["COL_LC"]["last_index"],
        "output_buffer_full": config["buffer_config"]["buffer5"]["buf_full_last_index"],
        "output_row": config["buffer_loop_configs"]["GROUP1"]["ROW_LC"]["last_index"],
        "output_col": config["buffer_loop_configs"]["GROUP1"]["COL_LC"]["last_index"],
    }
    expected_completion = {
        "read_stream_full": 2,
        "input_buffer_full": 2,
        "input_row": 2,
        "input_col": 3,
        "output_buffer_full": 3,
        "output_row": 3,
        "output_col": 4,
    }
    if completion != expected_completion:
        raise SumConfigAuditError(
            f"{template_name} completion-event references differ: {completion}"
        )


def validate_sum_template(config: dict[str, Any], template_name: str) -> dict[str, Any]:
    """Strict candidate preflight; it intentionally makes no numerical claim."""

    if template_name not in SUM_TEMPLATE_NAMES:
        raise SumConfigAuditError(f"unsupported sum template: {template_name}")
    try:
        structural = _validate_ga_template(
            config,
            label=template_name,
            allowed_ga_opcodes={"mul", "sum", "summac", "rec"},
        )
    except TargetConfigAuditError as error:
        raise SumConfigAuditError(str(error)) from error
    _validate_topology(config, template_name)
    return {
        "status": "candidate_preflight_valid",
        "numerical_status": "not_validated",
        "no_gate_authority": True,
        "family": _family(template_name),
        "resources": structural["resources"],
        "ga_opcodes": structural["ga_opcodes"],
    }


def _handler_audit(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "model_execplan" / "src" / "execution_plan_generator" / "control_registers.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    records: dict[str, dict[str, Any]] = {}
    for template_name in SUM_TEMPLATE_NAMES:
        function_name = _HANDLERS.get(template_name)
        function = functions.get(function_name) if function_name else None
        fields: set[str] = set()
        if function is not None:
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            fields.add(key.value)
        fields_sorted = sorted(fields)
        records[template_name] = {
            "handler_exists": function is not None,
            "handler_name": function_name,
            "docstring": ast.get_docstring(function) if function is not None else None,
            "update_fields": fields_sorted,
            "updates_output_shape_fields": any(
                field.startswith("wr_stream") or "iga_lc3" in field or "iga_lc4" in field
                for field in fields_sorted
            ),
            "updates_ga_or_requant_fields": any(
                "general_array" in field or "constant" in field for field in fields_sorted
            ),
            "uses_output_dimensions_in_updates": bool(
                function
                and any(
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id in {"d_k", "d_m", "d_n"}
                    for node in ast.walk(function)
                )
            ),
        }
    return records


def _base_info_audit(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "model_execplan" / "config" / "operator_base_info.json"
    operators = json.loads(path.read_text(encoding="utf-8"))["operators"]
    out: dict[str, dict[str, Any]] = {}
    for template_name in SUM_TEMPLATE_NAMES:
        op_type = Path(template_name).stem
        raw = operators.get(op_type)
        initial_size = raw.get("initial_size") if raw else None
        streamed_targets = ["A", "D"]
        metadata_targets = sorted(initial_size) if initial_size else []
        conflicts = []
        if template_name == "prefill_remote_sum_4slice_fp16MN_fp32MN.json" and raw:
            conflicts.append(
                "base-info declares A/B/D all [1,32,16], but JSON streams only A and D and "
                "does not describe a 4-to-1 output reduction"
            )
        out[template_name] = {
            "registered": raw is not None,
            "initial_size": initial_size,
            "streamed_targets": streamed_targets,
            "metadata_targets": metadata_targets,
            "conflicts": conflicts,
        }
    return out


def _template_record(
    source_root: Path,
    template_name: str,
    handler: dict[str, Any],
    base_info: dict[str, Any],
) -> dict[str, Any]:
    path = source_root / "jsons" / template_name
    config = json.loads(path.read_text(encoding="utf-8"))
    preflight = validate_sum_template(config, template_name)
    family = _family(template_name)
    ga = config["general_array"]
    pes = ga["PE_array"]
    reduction_pes = sorted(
        name for name, pe in pes.items() if pe["alu_opcode"] in {"sum", "summac"}
    )
    input_dtype = "fp16" if "fp16" in template_name else "fp32"
    if template_name == "sum_config_32_32.json":
        input_dtype = "fp32_assumed_from_sum_opcode_and_no_conversion"
    reduction_axis = {
        "local_sum": "candidate A[1] of a 32x32 matrix; not registered or handler-bound",
        "summac": "prefill graph indicates A[2] reduction while A[1] is preserved as D[2]; decode axis is unbound",
        "sum_rec": "prefill softmax graph indicates A[2] reduction followed by reciprocal; decode axis is unbound",
        "remote_sum": "prefill A[1] staged slice/group dimension; decode axis is unbound",
    }[family]
    lc_ends = {
        name: loop["end"] for name, loop in config["dram_loop_configs"].items()
    }
    return {
        "template": f"jsons/{template_name}",
        "sha256": sha256_file(path),
        "classification": (
            "resnet_or_shared_candidate"
            if template_name == "sum_config_32_32.json"
            else "deepseek_transformer_static"
        ),
        "preflight": preflight,
        "dtype": {
            "input": input_dtype,
            "output": "fp32_no_outport_conversion",
            "requant_present": False,
        },
        "reduction": {
            "axis_evidence": reduction_axis,
            "static_dram_lc_ends": lc_ends,
            "ga_reduction_pes": reduction_pes,
            "ga_opcode_counts": dict(sorted(Counter(pe["alu_opcode"] for pe in pes.values()).items())),
        },
        "cross_slice": {
            "remote_named": family == "remote_sum",
            "neighbor_or_n2n_config_present": False,
            "ga_neighbor_enabled": False,
            "buffer_neighbor_enabled": False,
            "conclusion": (
                "remote template reduces values already staged in A; transport between slices is outside this JSON"
                if family == "remote_sum"
                else "no direct cross-slice transport is encoded"
            ),
            "hardware_topology_validated": False,
        },
        "completion_events": {
            "ga_reduction_transout_last_index": 1,
            "read_and_input_buffer_full_last_index": 2,
            "input_buffer_col_last_index": 3,
            "output_buffer_full_and_row_last_index": 3,
            "output_buffer_col_last_index": 4,
            "scope": "static last_index reference chain only",
            "hardware_completion_protocol_validated": False,
        },
        "base_info": base_info,
        "handler": handler,
        "resnet_gap_relevance": {
            "candidate_part": template_name == "sum_config_32_32.json",
            "direct_gap_template": False,
            "reason": (
                "shared local FP32 sum may inform a reduction stage, but ResNet GAP needs UINT8/INT32 accumulation, division, qparams, requant and UINT8 output"
                if template_name == "sum_config_32_32.json"
                else "template is a DeepSeek FP16/FP32 reduction; no ResNet UINT8/INT32 or requant path"
            ),
        },
    }


def audit_sum_encoder(
    source_root: Path,
    template_names: Iterable[str] = SUM_TEMPLATE_NAMES,
) -> dict[str, Any]:
    """Run only the official encoder in temporary directories; no numerical execution."""

    names = tuple(sorted(template_names))
    unknown = sorted(set(names) - set(SUM_TEMPLATE_NAMES))
    if unknown:
        raise SumConfigAuditError(f"unsupported encoder templates: {unknown}")
    records: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rtl28-sum-audit-") as temp_text:
        temp = Path(temp_text)
        for template_name in names:
            template_path = source_root / "jsons" / template_name
            config = json.loads(template_path.read_text(encoding="utf-8"))
            validate_sum_template(config, template_name)
            first = _run_encoder(source_root, template_path, temp / Path(template_name).stem / "a")
            second = _run_encoder(source_root, template_path, temp / Path(template_name).stem / "b")
            if first["outputs"] != second["outputs"]:
                raise SumConfigAuditError(f"{template_name} official encoder outputs are not deterministic")
            records[template_name] = {
                "status": "encoding_deterministic",
                "run_count": 2,
                "environment": {"PYTHONHASHSEED": "0", "PYTHONUTF8": "1"},
                "mapper_seed": 42,
                "outputs": first["outputs"],
                "meaning": "encoding_and_zero_violation_placement_only",
                "numerical_status": "not_validated",
                "no_gate_authority": True,
            }
    return records


def _negative_preflight(source_root: Path) -> list[dict[str, str]]:
    path = source_root / "jsons" / "sum_config_32_32.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    mutations = []

    overflow = deepcopy(config)
    overflow["dram_loop_configs"]["LC1"]["end"] = 1 << 17
    mutations.append(("17-bit LC overflow", overflow))

    wrong_opcode = deepcopy(config)
    wrong_opcode["general_array"]["PE_array"]["PE00"]["alu_opcode"] = "max"
    mutations.append(("wrong GA opcode", wrong_opcode))

    requant = deepcopy(config)
    requant["general_array"]["outport"]["int32touint8"] = "true"
    mutations.append(("unapproved requant output", requant))

    records = []
    for label, value in mutations:
        try:
            validate_sum_template(value, "sum_config_32_32.json")
        except SumConfigAuditError as error:
            records.append({"mutation": label, "status": "rejected", "reason": str(error)})
        else:
            raise SumConfigAuditError(f"negative preflight was accepted: {label}")
    return records


def build_sum_config_audit(
    source_root: Path,
    *,
    run_encoder: bool = False,
    encoder_templates: Iterable[str] = SUM_TEMPLATE_NAMES,
) -> dict[str, Any]:
    """Build a deterministic, JSON-serializable C6 candidate report."""

    source_root = source_root.resolve()
    handlers = _handler_audit(source_root)
    base_info = _base_info_audit(source_root)
    templates = [
        _template_record(source_root, name, handlers[name], base_info[name])
        for name in SUM_TEMPLATE_NAMES
    ]
    report = {
        "schema_version": "0.1",
        "audit_id": "w4-28-c6-sum-config-candidate",
        "authority": {
            "status": "candidate_preflight_only",
            "numerical_status": "not_validated",
            "hardware_status": "not_validated",
            "no_gate_authority": True,
            "w5_authorized": False,
        },
        "scope": {
            "template_count": len(templates),
            "families": ["local_sum", "remote_sum", "sum_rec", "summac"],
            "formal_w5_instances_generated": False,
        },
        "templates": templates,
        "family_conclusions": {
            "local_sum": "sum_config_32_32 is the only shared/ResNet candidate, but it is FP32-only, unregistered and has no handler",
            "remote_sum": "28/4-way names describe staged-input reduction; no neighbor/N2N transport is present in the templates",
            "summac": "mul feeds both summac inputs, forming square accumulation used by DeepSeek RMSNorm",
            "sum_rec": "sum feeds REC/SFU for DeepSeek softmax; this is not GAP division/requant",
            "resnet_gap": "no audited sum template directly implements UINT8 GAP to UINT8; avgpool's INT32 sum still needs division and requant",
        },
        "handler_gaps": {
            "sum_config_missing_handler": True,
            "decode_templates_missing_base_info": True,
            "output_shape_not_used_by_any_sum_handler": True,
            "output_stream_buffer_geometry_not_patched": True,
            "fp16_remote_4slice_metadata_conflict": True,
            "dtype_and_divisibility_preconditions_not_enforced": True,
        },
        "negative_preflight": _negative_preflight(source_root),
        "encoder_probe": (
            audit_sum_encoder(source_root, encoder_templates)
            if run_encoder
            else {
                "status": "not_run",
                "numerical_status": "not_validated",
                "no_gate_authority": True,
            }
        ),
    }
    json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return report
