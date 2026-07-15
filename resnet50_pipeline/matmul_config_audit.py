from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .source_versions import (
    OFFICIAL_CONFIG_COMMIT,
    OFFICIAL_EXECPLAN_COMMIT,
    SourceVersionError,
    verify_ndp_source_checkout,
)


PRIMARY_GEMV_TEMPLATE = "gemv_config_local_M1N128K32.json"
SA_TEMPLATES: dict[str, dict[str, Any]] = {
    "decode_gemv_local.json": {
        "mode": "gemv", "shape_key": "gemv_shape", "shape": {"M": 1, "N": 32, "K": 32},
        "has_ga": True, "ring_slices": None, "output_dtype": "fp16",
        "handler": "decode_gemv_local",
    },
    "decode_gemv_ring.json": {
        "mode": "gemv", "shape_key": "gemv_shape", "shape": {"M": 1, "N": 32, "K": 224},
        "has_ga": True, "ring_slices": 28, "output_dtype": "fp16",
        "handler": "decode_gemv_ring",
    },
    PRIMARY_GEMV_TEMPLATE: {
        "mode": "gemv", "shape_key": "gemv_shape", "shape": {"M": 1, "N": 128, "K": 32},
        "has_ga": False, "ring_slices": None, "output_dtype": "fp16",
        "handler": None,
    },
    "prefill_gemm_local.json": {
        "mode": "gemm", "shape_key": "gemm_shape", "shape": {"M": 64, "N": 64, "K": 32},
        "has_ga": False, "ring_slices": None, "output_dtype": "fp16",
        "handler": "prefill_gemm_local",
    },
    "prefill_gemm_local_qkt.json": {
        "mode": "gemm", "shape_key": "gemm_shape", "shape": {"M": 32, "N": 32, "K": 32},
        "has_ga": False, "ring_slices": None, "output_dtype": "fp32",
        "handler": "prefill_gemm_local_qkt",
    },
    "prefill_gemm_ring_4slice.json": {
        "mode": "gemm", "shape_key": "gemm_shape", "shape": {"M": 64, "N": 32, "K": 16},
        "has_ga": False, "ring_slices": 4, "output_dtype": "fp16",
        "handler": "prefill_gemm_ring_4slice",
    },
}

_HANDLER_FUNCTIONS = {
    name: f"_compute_{name}_control_register_updates"
    for name in (
        "prefill_gemm_local", "prefill_gemm_ring_4slice", "prefill_gemm_local_qkt",
        "decode_gemv_local", "decode_gemv_ring",
    )
}
_REGISTER_FIELD = re.compile(
    r"^(?:iga_|rd_stream|wr_stream|se_nse|buffer_manager_cluster|special_array)"
)


class MatmulConfigAuditError(RuntimeError):
    pass


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatmulConfigAuditError(f"{path} must be an object")
    return value


def _exact(value: dict[str, Any], keys: set[str], path: str) -> None:
    if set(value) != keys:
        raise MatmulConfigAuditError(
            f"{path} fields differ: missing={sorted(keys - set(value))}, "
            f"unexpected={sorted(set(value) - keys)}"
        )


def _uint(value: Any, width: int, path: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << width):
        raise MatmulConfigAuditError(
            f"{path} must fit unsigned {width}-bit range; refusing silent truncation"
        )


def _bit_list(value: Any, length: int, path: str) -> None:
    if not isinstance(value, list) or len(value) != length or any(v not in (0, 1) for v in value):
        raise MatmulConfigAuditError(f"{path} must contain {length} binary values")


def _bool_flag(value: Any, path: str) -> None:
    if value not in (True, False, "true", "false"):
        raise MatmulConfigAuditError(f"{path} must be boolean")


def _base_addr(value: Any, path: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip().replace("_", "")
        if not raw.lower().startswith("0b") or len(raw[2:]) != 30 or set(raw[2:]) - {"0", "1"}:
            raise MatmulConfigAuditError(f"{path} must be an exact 30-bit binary literal")
        parsed = int(raw[2:], 2)
    else:
        raise MatmulConfigAuditError(f"{path} must be an integer or binary literal")
    _uint(parsed, 30, path)
    if parsed % 16:
        raise MatmulConfigAuditError(f"{path} must be 16-byte aligned")
    return parsed


def _validate_port(value: Any, path: str) -> None:
    port = _object(value, path)
    _exact(port, {"src_id", "mode", "keep_last_index", "constant"}, path)
    if port["mode"] not in (None, "buffer", "keep", "constant"):
        raise MatmulConfigAuditError(f"{path}.mode is unsupported")
    _uint(port["keep_last_index"], 4, f"{path}.keep_last_index", nullable=True)
    constant = port["constant"]
    if isinstance(constant, bool) or not isinstance(constant, (int, float)):
        raise MatmulConfigAuditError(f"{path}.constant must be numeric")
    if isinstance(constant, int) and not -(1 << 15) <= constant < (1 << 16):
        raise MatmulConfigAuditError(f"{path}.constant exceeds the encoded field")


def _validate_stream(value: Any, path: str) -> tuple[str, str]:
    stream = _object(value, path)
    mode = stream.get("mode")
    common = {
        "target", "mode", "base_addr", "mem_idx_mode", "mem_idx_keep_last_index",
        "mem_idx_constant", "idx", "idx_size", "dim_stride", "tailing_enable",
        "idx_tailing_range", "address_remapping", "buf_idx_mode",
        "buf_idx_keep_last_index", "buf_spatial_stride", "buf_spatial_size",
        "ping_pong", "pingpong_last_index",
    }
    read = {"padding_enable", "padding_reg_value", "idx_padding_range", "buf_full_last_index"}
    if mode not in ("read", "write"):
        raise MatmulConfigAuditError(f"{path}.mode must be read or write")
    _exact(stream, common | (read if mode == "read" else set()), path)
    if stream["target"] not in ("A", "B", "B'", "D"):
        raise MatmulConfigAuditError(f"{path}.target is unsupported")
    _base_addr(stream["base_addr"], f"{path}.base_addr")
    for field, length, width in (
        ("idx_size", 3, 8), ("dim_stride", 3, 20),
        ("mem_idx_keep_last_index", 3, 4), ("buf_idx_keep_last_index", 2, 4),
    ):
        values = stream[field]
        if not isinstance(values, list) or len(values) != length:
            raise MatmulConfigAuditError(f"{path}.{field} must contain {length} values")
        for index, item in enumerate(values):
            _uint(item, width, f"{path}.{field}[{index}]", nullable=True)
    _bit_list(stream["tailing_enable"], 3, f"{path}.tailing_enable")
    if mode == "read":
        _bit_list(stream["padding_enable"], 3, f"{path}.padding_enable")
        _uint(stream["padding_reg_value"], 8, f"{path}.padding_reg_value", nullable=True)
        _uint(stream["buf_full_last_index"], 4, f"{path}.buf_full_last_index")
    spatial = stream["buf_spatial_stride"]
    if not isinstance(spatial, list) or len(spatial) > 16:
        raise MatmulConfigAuditError(f"{path}.buf_spatial_stride exceeds 16 entries")
    for index, item in enumerate(spatial):
        _uint(item, 5, f"{path}.buf_spatial_stride[{index}]")
    _uint(stream["buf_spatial_size"], 5, f"{path}.buf_spatial_size")
    _uint(stream["ping_pong"], 1, f"{path}.ping_pong")
    _uint(stream["pingpong_last_index"], 4, f"{path}.pingpong_last_index", nullable=True)
    return mode, stream["target"]


def _validate_special_array(value: Any, expected_mode: str) -> dict[str, Any]:
    sa = _object(value, "special_array")
    _exact(
        sa,
        {"mode", "inport0", "inport1", "inport2", "data_type", "transout_last_index", "bias_enable", "outport"},
        "special_array",
    )
    if sa["mode"] != expected_mode:
        raise MatmulConfigAuditError("special_array.mode conflicts with the template family")
    if sa["data_type"] != "fp16":
        raise MatmulConfigAuditError("locked SA candidate must remain fp16; INT8 is not validated")
    _uint(sa["transout_last_index"], 4, "special_array.transout_last_index")
    _uint(sa["bias_enable"], 1, "special_array.bias_enable")
    for name in ("inport0", "inport1", "inport2"):
        port = _object(sa[name], f"special_array.{name}")
        _exact(port, {"enable", "pingpong_en", "pingpong_last_index", "nbr_enable"}, f"special_array.{name}")
        for field in ("enable", "pingpong_en", "nbr_enable"):
            _uint(port[field], 1, f"special_array.{name}.{field}")
        _uint(port["pingpong_last_index"], 4, f"special_array.{name}.pingpong_last_index", nullable=True)
    outport = _object(sa["outport"], "special_array.outport")
    _exact(outport, {"mode", "fp32tofp16", "fp32tobf16"}, "special_array.outport")
    if outport["mode"] not in ("row", "col"):
        raise MatmulConfigAuditError("special_array.outport.mode is unsupported")
    _bool_flag(outport["fp32tofp16"], "special_array.outport.fp32tofp16")
    _bool_flag(outport["fp32tobf16"], "special_array.outport.fp32tobf16")
    if sa["bias_enable"] != 0 or sa["inport2"]["enable"] != 0:
        raise MatmulConfigAuditError("locked templates do not validate a bias/psum inport")
    return sa


def _validate_ga_bridge(value: Any) -> dict[str, Any]:
    ga = _object(value, "general_array")
    _exact(ga, {"inport", "outport", "PE_array"}, "general_array")
    inports = _object(ga["inport"], "general_array.inport")
    outport = _object(ga["outport"], "general_array.outport")
    pes = _object(ga["PE_array"], "general_array.PE_array")
    if set(pes) != {f"PE{r}{c}" for r in range(4) for c in (0, 2)}:
        raise MatmulConfigAuditError("decode GEMV GA bridge must use the eight locked sum lanes")
    if any(pe.get("alu_opcode") != "sum" for pe in pes.values()):
        raise MatmulConfigAuditError("decode GEMV GA bridge must use sum")
    if set(inports) != {"inport0", "inport1", "inport2"}:
        raise MatmulConfigAuditError("decode GEMV GA inport set differs")
    if inports["inport0"].get("src_id") != 1 or inports["inport0"].get("mask") != [1] * 8:
        raise MatmulConfigAuditError("SA-to-GA bridge must enter GA inport0 from source 1")
    if outport.get("src_id") != 0 or outport.get("mask") != [1] * 8:
        raise MatmulConfigAuditError("GA-to-D bridge differs from the locked template")
    if outport.get("int32touint8") not in (False, "false"):
        raise MatmulConfigAuditError("decode GEMV candidate must not be relabeled as requantized UINT8")
    return ga


def validate_matmul_template(config: dict[str, Any], template_name: str) -> dict[str, Any]:
    """Strict preflight for one of the six locked SA candidates."""

    if template_name not in SA_TEMPLATES:
        raise MatmulConfigAuditError(f"unsupported SA template: {template_name}")
    spec = SA_TEMPLATES[template_name]
    top = {
        "CONFIG", "dram_loop_configs", "lc_pe_configs", "buffer_loop_configs",
        "buffer_config", "stream_engine", "special_array", spec["shape_key"],
    }
    if spec["has_ga"]:
        top.add("general_array")
    if spec["ring_slices"] is not None:
        top.add("n2n")
    _exact(config, top, f"{template_name} config")
    if not isinstance(config["CONFIG"], str) or len(config["CONFIG"]) != 8 or set(config["CONFIG"]) - {"0", "1"}:
        raise MatmulConfigAuditError("CONFIG must be an eight-bit binary string")
    if config[spec["shape_key"]] != spec["shape"]:
        raise MatmulConfigAuditError("static shape metadata differs from the locked candidate")

    dram = _object(config["dram_loop_configs"], "dram_loop_configs")
    if len(dram) > 20 or any(re.fullmatch(r"LC\d+", name) is None for name in dram):
        raise MatmulConfigAuditError("invalid DRAM loop resource set")
    for name, raw in dram.items():
        loop = _object(raw, f"dram_loop_configs.{name}")
        _exact(loop, {"src_id", "outmost_loop", "start", "end", "stride", "last_index"}, f"dram_loop_configs.{name}")
        _uint(loop["outmost_loop"], 1, f"dram_loop_configs.{name}.outmost_loop")
        for field in ("end", "stride"):
            _uint(loop[field], 17, f"dram_loop_configs.{name}.{field}")
        _uint(loop["last_index"], 4, f"dram_loop_configs.{name}.last_index")

    lcpes = _object(config["lc_pe_configs"], "lc_pe_configs")
    if len(lcpes) > 10 or any(re.fullmatch(r"PE\d+", name) is None for name in lcpes):
        raise MatmulConfigAuditError("invalid LC PE resource set")
    for name, raw in lcpes.items():
        pe = _object(raw, f"lc_pe_configs.{name}")
        _exact(pe, {"alu_opcode", "inport0", "inport1", "inport2"}, f"lc_pe_configs.{name}")
        if pe["alu_opcode"] not in ("mac", "mul"):
            raise MatmulConfigAuditError(f"lc_pe_configs.{name}.alu_opcode is unsupported")
        for index in range(3):
            _validate_port(pe[f"inport{index}"], f"lc_pe_configs.{name}.inport{index}")

    groups = _object(config["buffer_loop_configs"], "buffer_loop_configs")
    if set(groups) != {"GROUP0", "GROUP1", "GROUP2", "GROUP3"}:
        raise MatmulConfigAuditError("SA template must bind four buffer loop groups")
    if {group.get("target") for group in groups.values()} != {"A", "B", "B'", "D"}:
        raise MatmulConfigAuditError("buffer loop targets must be A/B/B'/D")
    for name, raw in groups.items():
        group = _object(raw, f"buffer_loop_configs.{name}")
        _exact(group, {"target", "ROW_LC", "COL_LC"}, f"buffer_loop_configs.{name}")
        for kind, width in (("ROW_LC", 3), ("COL_LC", 6)):
            loop = _object(group[kind], f"buffer_loop_configs.{name}.{kind}")
            _exact(loop, {"src_id", "start", "end", "stride", "last_index"}, f"buffer_loop_configs.{name}.{kind}")
            for field in ("start", "end", "stride"):
                _uint(loop[field], width, f"buffer_loop_configs.{name}.{kind}.{field}")
            _uint(loop["last_index"], 4, f"buffer_loop_configs.{name}.{kind}.last_index")

    streams = _object(config["stream_engine"], "stream_engine")
    if set(streams) != {"stream0", "stream1", "stream2", "stream3"}:
        raise MatmulConfigAuditError("SA template must bind four streams")
    stream_roles = [_validate_stream(streams[name], f"stream_engine.{name}") for name in sorted(streams)]
    if sorted(stream_roles) != sorted([("read", "A"), ("read", "B"), ("read", "B'"), ("write", "D")]):
        raise MatmulConfigAuditError("stream roles must be read A/B/B' and write D")

    buffers = _object(config["buffer_config"], "buffer_config")
    if set(buffers) != {f"buffer{i}" for i in range(6)}:
        raise MatmulConfigAuditError("SA template must configure all six buffers")
    for name, raw in buffers.items():
        buffer = _object(raw, f"buffer_config.{name}")
        required = {"dst_port", "nbr_enable", "buf_full_last_index", "buffer_life_time", "mode", "mask", "buf_end_row_addr"}
        if not required.issubset(buffer) or set(buffer) - (required | {"buffer_nbr_cnt"}):
            raise MatmulConfigAuditError(f"buffer_config.{name} fields differ")
        for field, width in (("dst_port", 1), ("nbr_enable", 1), ("buf_full_last_index", 4), ("mode", 1), ("buf_end_row_addr", 2)):
            _uint(buffer[field], width, f"buffer_config.{name}.{field}")
        # The official encoder stores value-1 in four bits, so the JSON domain is 1..16.
        if isinstance(buffer["buffer_life_time"], bool) or not isinstance(buffer["buffer_life_time"], int) or not 1 <= buffer["buffer_life_time"] <= 16:
            raise MatmulConfigAuditError(f"buffer_config.{name}.buffer_life_time must be in 1..16")
        _bit_list(buffer["mask"], 8, f"buffer_config.{name}.mask")
        if "buffer_nbr_cnt" in buffer:
            _uint(buffer["buffer_nbr_cnt"], 5, f"buffer_config.{name}.buffer_nbr_cnt", nullable=True)

    sa = _validate_special_array(config["special_array"], spec["mode"])
    if spec["ring_slices"] is not None:
        n2n = _object(config["n2n"], "n2n")
        _exact(n2n, {"neighbor_stream0"}, "n2n")
        neighbor = _object(n2n["neighbor_stream0"], "n2n.neighbor_stream0")
        _exact(neighbor, {"src_slice_sel", "dst_slice_sel", "ping_pong", "mem_loop"}, "n2n.neighbor_stream0")
        for field in ("src_slice_sel", "dst_slice_sel", "ping_pong"):
            _uint(neighbor[field], 1, f"n2n.neighbor_stream0.{field}")
        _uint(neighbor["mem_loop"], 5, "n2n.neighbor_stream0.mem_loop")
        if neighbor["mem_loop"] != spec["ring_slices"]:
            raise MatmulConfigAuditError("n2n.mem_loop differs from the locked ring size")
    if spec["has_ga"]:
        _validate_ga_bridge(config["general_array"])
        if config["buffer_config"]["buffer5"]["dst_port"] != 1:
            raise MatmulConfigAuditError("decode GEMV buffer5 must bridge SA output into GA")

    return {
        "status": "passed",
        "identity": "locked_static_candidate",
        "template": template_name,
        "shape": dict(spec["shape"]),
        "shape_metadata_is_encoder_control": False,
        "resources": {
            "dram_loops": len(dram), "lc_pes": len(lcpes), "buffer_groups": len(groups),
            "streams": len(streams), "buffers": len(buffers), "ga_bridge": spec["has_ga"],
            "n2n_ring_slices": spec["ring_slices"],
        },
        "sa": {
            "mode": sa["mode"], "input_dtype": "fp16", "accumulator_dtype": "not_proven_by_json",
            "output_dtype": spec["output_dtype"], "bias_enable": False,
            "external_psum_input": False, "requant_to_uint8": False,
        },
        "scope": "structure_ranges_locked_instance_crosswalk_only",
        "numerical_status": "not_validated",
        "no_gate_authority": True,
    }


def inventory_sa_templates(source_root: Path) -> dict[str, Any]:
    found = []
    for path in sorted((source_root / "jsons").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if "special_array" in value:
            found.append(path.name)
    expected = sorted(SA_TEMPLATES)
    if found != expected:
        raise MatmulConfigAuditError(f"SA inventory differs: expected={expected}, actual={found}")
    return {
        "status": "passed", "candidate_count": len(found), "templates": found,
        "gemm_count": sum(SA_TEMPLATES[name]["mode"] == "gemm" for name in found),
        "gemv_count": sum(SA_TEMPLATES[name]["mode"] == "gemv" for name in found),
        "all_static_data_type": "fp16", "all_static_bias_enable": 0,
        "named_int8_template_count": 0,
    }


def _extract_handler_audit(source_root: Path) -> dict[str, Any]:
    control_path = source_root / "model_execplan" / "src" / "execution_plan_generator" / "control_registers.py"
    text = control_path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    handlers: dict[str, Any] = {}
    for op_type, function_name in sorted(_HANDLER_FUNCTIONS.items()):
        node = functions.get(function_name)
        if node is None:
            raise MatmulConfigAuditError(f"missing execplan handler: {function_name}")
        segment = ast.get_source_segment(text, node) or ""
        fields = sorted({
            item.value for item in ast.walk(node)
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and _REGISTER_FIELD.match(item.value)
        })
        handlers[op_type] = {
            "exists": True,
            "declared_placeholder": "Placeholder" in (ast.get_docstring(node) or ""),
            "patched_field_count": len(fields),
            "patched_fields": fields,
            "typed_qparams_consumed": any(token in segment for token in ("scale", "zero_point", "qparam")),
            "tail_remainder_guard": "%" in segment or "remainder" in segment,
        }

    model_path = source_root / "model_execplan" / "src" / "execution_plan_generator" / "models.py"
    model_tree = ast.parse(model_path.read_text(encoding="utf-8"))
    operator_fields: list[str] = []
    for node in model_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "OperatorSpec":
            operator_fields = [
                child.target.id for child in node.body
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name)
            ]
    base_info = json.loads(
        (source_root / "model_execplan" / "config" / "operator_base_info.json").read_text(encoding="utf-8")
    )["operators"]
    registered = sorted(name for name in base_info if "gemm" in name or "gemv" in name)
    return {
        "status": "typed_transport_available_operator_handlers_partial",
        "source": "model_execplan/src/execution_plan_generator/control_registers.py",
        "source_sha256": sha256_file(control_path),
        "handler_count": len(handlers),
        "handlers": handlers,
        "operator_spec_fields": operator_fields,
        "operator_spec_has_typed_qparams": any(name in operator_fields for name in ("qparams", "attributes", "constants")),
        "generic_typed_constant_consumer": (
            "_append_typed_constant_register_updates" in text
            and "control_register:" in text
        ),
        "operator_base_info_registered_types": registered,
        "templates_without_registered_operator_type": sorted(
            name for name, spec in SA_TEMPLATES.items()
            if spec["handler"] is None or spec["handler"] not in registered
        ),
        "interpretation": "handler existence does not prove complete shape, dtype, tail, qparam, or numerical rules",
    }


def extract_matmul_crosswalk(source_root: Path) -> dict[str, Any]:
    templates: dict[str, Any] = {}
    for name in sorted(SA_TEMPLATES):
        path = source_root / "jsons" / name
        config = json.loads(path.read_text(encoding="utf-8"))
        preflight = validate_matmul_template(config, name)
        streams = config["stream_engine"]
        templates[name] = {
            "sha256": sha256_file(path),
            "preflight": preflight,
            "observed_chain": {
                "shape_metadata": dict(config[SA_TEMPLATES[name]["shape_key"]]),
                "lc_end": {key: value["end"] for key, value in sorted(config["dram_loop_configs"].items())},
                "stream": {
                    key: {
                        "target": value["target"], "mode": value["mode"],
                        "idx_size": value["idx_size"], "dim_stride": value["dim_stride"],
                        "buf_spatial_size": value["buf_spatial_size"],
                    }
                    for key, value in sorted(streams.items())
                },
                "buffer": {
                    key: {
                        "dst_port": value["dst_port"], "nbr_enable": value["nbr_enable"],
                        "buf_full_last_index": value["buf_full_last_index"],
                        "buffer_life_time": value["buffer_life_time"], "mask": value["mask"],
                    }
                    for key, value in sorted(config["buffer_config"].items())
                },
                "sa": {
                    "mode": config["special_array"]["mode"],
                    "data_type": config["special_array"]["data_type"],
                    "bias_enable": config["special_array"]["bias_enable"],
                    "inport2_enable": config["special_array"]["inport2"]["enable"],
                    "outport": dict(config["special_array"]["outport"]),
                },
                "ga_boundary": (
                    "SA_fp32_to_buffer5_to_GA_sum_to_fp16_D"
                    if SA_TEMPLATES[name]["has_ga"] else "direct_SA_to_D"
                ),
            },
        }
    return {
        "status": "candidate_preflight_passed",
        "rule_scope": "six_locked_static_SA_templates",
        "templates": templates,
        "handler_binding": _extract_handler_audit(source_root),
        "resnet_qlinearmatmul_gap": {
            "resnet_shape_MNK": [16, 1000, 2048],
            "onnx_input_contract": ["A", "a_scale", "a_zero_point", "B", "b_scale", "b_zero_point", "y_scale", "y_zero_point"],
            "required_dtype_path": ["uint8_A", "uint8_B", "int32_accumulator", "uint8_D"],
            "static_candidate_dtype_path": ["fp16_A", "fp16_B", "unproven_SA_accumulator", "fp16_or_fp32_D"],
            "local_gemm_floor_projection": {
                "M_div_32": 0, "M_remainder_32": 16,
                "N_div_32": 31, "N_remainder_32": 8,
                "K_div_2": 1024, "K_div_4": 512,
            },
            "missing": [
                "validated INT8 SA template and INT32 accumulator contract",
                "M=16 and N=1000 tail rules; current floor divisions would omit work",
                "input zero-point correction for both operands",
                "typed a/b/y qparams scale and zero-point binding",
                "external or persistent INT32 psum first/middle/last-K lifecycle",
                "INT32-to-UINT8 nearest-even requantization and saturation",
                "numerically validated SA-to-GA requant boundary",
            ],
            "bias": {
                "qlinearmatmul_has_bias_input": False,
                "resnet_dense_bias_location": "following QLinearAdd",
                "static_sa_bias_enable": 0,
                "fusion_supported": False,
            },
            "ring_observation": "N2N moves an SA operand in the static ring candidates; no explicit cross-slice INT32 psum stream is proven",
            "complete_compatible_template_exists": False,
        },
        "numerical_status": "not_validated",
        "no_gate_authority": True,
    }


def _verify_source(source_root: Path) -> None:
    try:
        verify_ndp_source_checkout(source_root)
    except SourceVersionError as error:
        raise MatmulConfigAuditError(str(error)) from error


def _run_encoder(source_root: Path, config_path: Path, output_dir: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONHASHSEED": "0"})
    completed = subprocess.run(
        [
            sys.executable, "-m", "bitstream.main", "-c", str(config_path), "-o", str(output_dir),
            "--seed", "42", "--heuristic-iterations", "10000", "--heuristic-restarts", "10", "--quiet",
        ],
        cwd=source_root, env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False, timeout=120,
    )
    if completed.returncode or "Mapping successful with zero violations" not in completed.stdout:
        raise MatmulConfigAuditError(f"official encoder failed: {(completed.stderr or completed.stdout)[-2000:]}")
    outputs = {
        path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(output_dir.iterdir()) if path.is_file()
    }
    return {"outputs": outputs, "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest()}


def audit_matmul_encoder(source_root: Path, template_name: str = PRIMARY_GEMV_TEMPLATE) -> dict[str, Any]:
    """Encode only in TemporaryDirectory; success remains non-numerical evidence."""

    _verify_source(source_root)
    if template_name not in SA_TEMPLATES:
        raise MatmulConfigAuditError(f"unsupported SA template: {template_name}")
    path = source_root / "jsons" / template_name
    config = json.loads(path.read_text(encoding="utf-8"))
    validation = validate_matmul_template(config, template_name)
    with tempfile.TemporaryDirectory(prefix="rtl28-matmul-audit-") as text:
        temp = Path(text)
        first = _run_encoder(source_root, path, temp / "first")
        second = _run_encoder(source_root, path, temp / "second")
        if first["outputs"] != second["outputs"]:
            raise MatmulConfigAuditError("official encoder outputs are not deterministic")
        changed = deepcopy(config)
        original = _base_addr(changed["stream_engine"]["stream0"]["base_addr"], "stream0.base_addr")
        changed["stream_engine"]["stream0"]["base_addr"] = original + 16
        validate_matmul_template(changed, template_name)
        changed_path = temp / "changed.json"
        changed_path.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
        different = _run_encoder(source_root, changed_path, temp / "different")
        baseline_bins = sorted(v["sha256"] for k, v in first["outputs"].items() if k.endswith("_bitstream_128b.bin"))
        changed_bins = sorted(v["sha256"] for k, v in different["outputs"].items() if k.endswith("_bitstream_128b.bin"))
        if not baseline_bins or baseline_bins == changed_bins:
            raise MatmulConfigAuditError("base-address mutation did not change the encoded 128b bitstream")
    invalid = deepcopy(config)
    invalid["dram_loop_configs"][sorted(invalid["dram_loop_configs"])[0]]["end"] = 1 << 17
    try:
        validate_matmul_template(invalid, template_name)
    except MatmulConfigAuditError as error:
        rejection = str(error)
    else:
        raise MatmulConfigAuditError("overflow mutation was not rejected")
    return {
        "status": "candidate_encoder_preflight_passed",
        "template": template_name,
        "preflight": validation,
        "determinism": {
            "status": "passed", "run_count": 2,
            "environment": {"PYTHONHASHSEED": "0", "PYTHONUTF8": "1"}, "seed": 42,
            "outputs": first["outputs"],
        },
        "differential_sensitivity": {
            "status": "passed", "field": "stream_engine.stream0.base_addr",
            "original": original, "modified": original + 16,
            "baseline_128b_sha256": baseline_bins, "modified_128b_sha256": changed_bins,
        },
        "fail_closed": {"status": "passed", "rejection": rejection},
        "numerical_status": "not_validated",
        "no_gate_authority": True,
    }


def build_matmul_candidate_report(source_root: Path, *, run_encoder: bool = False) -> dict[str, Any]:
    """Return a deterministic, JSON-serializable C6 candidate report."""

    _verify_source(source_root)
    report: dict[str, Any] = {
        "schema_version": "0.1",
        "report_kind": "w4_28_c6_matmul_candidate_audit",
        "source": {
            "repository": "ndp-sim-ref",
            "commit": OFFICIAL_CONFIG_COMMIT,
            "config_baseline_commit": OFFICIAL_CONFIG_COMMIT,
            "execplan_commit": OFFICIAL_EXECPLAN_COMMIT,
        },
        "status": "candidate_preflight_only",
        "inventory": inventory_sa_templates(source_root),
        "crosswalk": extract_matmul_crosswalk(source_root),
        "encoder_probe": {"status": "not_run", "reason": "optional_expensive_probe"},
        "numerical_status": "not_validated",
        "target_simulator_validated": False,
        "w5_instance_generated": False,
        "g4_authorized": False,
        "no_gate_authority": True,
    }
    if run_encoder:
        report["encoder_probe"] = audit_matmul_encoder(source_root)
    # Prove the public object has no accidental non-JSON values.
    json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return report
