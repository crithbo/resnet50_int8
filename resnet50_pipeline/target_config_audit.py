from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .hashing import sha256_file


OFFICIAL_CONFIG_REPOSITORY = "https://github.com/uSFrances/ndp-sim.git"
OFFICIAL_CONFIG_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
OFFICIAL_CONFIG_SLICE_COUNT = 28
MAXPOOL_TEMPLATE = "maxpool_config_16_112_112_stride2_padding1.json"
SECOND_MAXPOOL_TEMPLATE = "maxpool_config_16_16_16_stride2_padding1.json"
AVGPOOL_TEMPLATE = "avgpool_config_2048_7_7.json"
QUANT_TEMPLATE = "quant_from_buffer_int32MN_uint8MN.json"
ADD_DEQUANT_TEMPLATE = "add_dequant_uint8CWH_uint8CWH_fp32CWH.json"

_FP32_ROUND_MAGIC = 12_582_912.0
_FP32_ROUND_MAGIC_BITS = 0x4B400000
_QUANT_MAC_PES = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
_QUANT_SUB_PES = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
_ADD_DEQUANT_A_PES = ("PE00", "PE02", "PE20", "PE22")
_ADD_DEQUANT_B_PES = ("PE01", "PE03", "PE21", "PE23")
_ADD_DEQUANT_SUM_PES = ("PE10", "PE12", "PE30", "PE32")

_RESOURCE_PATTERNS = {
    "dram_loop_configs": (re.compile(r"LC\d+$"), 20),
    "lc_pe_configs": (re.compile(r"PE\d+$"), 10),
    "buffer_loop_configs": (re.compile(r"GROUP\d+$"), 5),
    "buffer_config": (re.compile(r"buffer[0-5]$"), 6),
}

_FIELD_ROUTES = {
    "dram_loop_configs": {
        "encoder_class": "DramLoopControlConfig",
        "source": "bitstream/config/loop.py",
        "resource_count": 20,
    },
    "lc_pe_configs": {
        "encoder_class": "LCPEConfig",
        "source": "bitstream/config/loop.py",
        "resource_count": 10,
    },
    "buffer_loop_configs": {
        "encoder_class": "BufferRowLCConfig+BufferColLCConfig",
        "source": "bitstream/config/loop.py",
        "resource_count": 5,
    },
    "stream_engine": {
        "encoder_class": "ReadStreamEngineConfig+WriteStreamEngineConfig",
        "source": "bitstream/config/stream.py",
        "resource_count": "4 read + 1 write",
    },
    "buffer_config": {
        "encoder_class": "BufferConfig",
        "source": "bitstream/config/buffer.py",
        "resource_count": 6,
    },
    "general_array.inport": {
        "encoder_class": "GAInportConfig",
        "source": "bitstream/config/general.py",
        "resource_count": 3,
    },
    "general_array.outport": {
        "encoder_class": "GAOutportConfig",
        "source": "bitstream/config/general.py",
        "resource_count": 1,
    },
    "general_array.PE_array": {
        "encoder_class": "GAPEConfig",
        "source": "bitstream/config/general.py",
        "resource_count": 16,
    },
}


class TargetConfigAuditError(RuntimeError):
    pass


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TargetConfigAuditError(f"{path} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise TargetConfigAuditError(
            f"{path} fields differ: missing={missing}, unexpected={extra}"
        )


def _uint(value: Any, width: int, path: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TargetConfigAuditError(f"{path} must be an unsigned {width}-bit integer")
    if not 0 <= value < 1 << width:
        raise TargetConfigAuditError(
            f"{path}={value} exceeds unsigned {width}-bit range; refusing silent truncation"
        )


def _signed_int(value: Any, width: int, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TargetConfigAuditError(f"{path} must be a signed {width}-bit integer")
    if not -(1 << (width - 1)) <= value < 1 << (width - 1):
        raise TargetConfigAuditError(f"{path}={value} exceeds signed {width}-bit range")


def _bits(value: Any, length: int, path: str) -> None:
    if not isinstance(value, list) or len(value) != length or any(v not in (0, 1) for v in value):
        raise TargetConfigAuditError(f"{path} must contain exactly {length} binary values")


def _base_address(value: Any, path: str) -> int:
    """Validate the official 30-bit address forms and return an integer value."""

    if isinstance(value, int) and not isinstance(value, bool):
        _uint(value, 30, path)
        parsed = value
    elif isinstance(value, str):
        compact = value.strip().replace("_", "")
        if not compact.lower().startswith("0b"):
            raise TargetConfigAuditError(
                f"{path} must be an integer or an exact 30-bit binary literal"
            )
        raw = compact[2:]
        if len(raw) != 30 or set(raw) - {"0", "1"}:
            raise TargetConfigAuditError(f"{path} must contain exactly 30 binary bits")
        parsed = int(raw, 2)
    else:
        raise TargetConfigAuditError(
            f"{path} must be an integer or an exact 30-bit binary literal"
        )
    if parsed % 16:
        raise TargetConfigAuditError(f"{path} must be 16-byte aligned")
    return parsed


def _resource_keys(config: dict[str, Any], group: str) -> dict[str, Any]:
    records = _mapping(config[group], group)
    pattern, limit = _RESOURCE_PATTERNS[group]
    if len(records) > limit:
        raise TargetConfigAuditError(f"{group} uses {len(records)} resources, hardware limit is {limit}")
    invalid = sorted(key for key in records if pattern.fullmatch(key) is None)
    if invalid:
        raise TargetConfigAuditError(f"{group} contains invalid resource names: {invalid}")
    return records


def _validate_loop_port(
    value: Any,
    path: str,
    *,
    src_width: int,
    constant_width: int,
) -> None:
    port = _mapping(value, path)
    _exact_keys(port, {"src_id", "mode", "keep_last_index", "constant"}, path)
    if port["mode"] not in (None, "buffer", "keep", "constant"):
        raise TargetConfigAuditError(f"{path}.mode is unsupported")
    _uint(port["keep_last_index"], 4, f"{path}.keep_last_index", nullable=True)
    src_id = port["src_id"]
    if src_id is not None and not isinstance(src_id, (str, int)):
        raise TargetConfigAuditError(f"{path}.src_id must be null, a source name, or an integer")
    if isinstance(src_id, int):
        _uint(src_id, src_width, f"{path}.src_id")
    constant = port["constant"]
    if isinstance(constant, bool):
        raise TargetConfigAuditError(f"{path}.constant must be a finite numeric value")
    if isinstance(constant, int):
        if not -(1 << (constant_width - 1)) <= constant < 1 << constant_width:
            raise TargetConfigAuditError(
                f"{path}.constant={constant} exceeds the {constant_width}-bit encoded field"
            )
    elif isinstance(constant, float):
        if not math.isfinite(constant):
            raise TargetConfigAuditError(f"{path}.constant must be finite")
        try:
            struct.pack("<f", constant)
        except OverflowError as error:
            raise TargetConfigAuditError(
                f"{path}.constant cannot be represented as fp32"
            ) from error
    elif constant is not None:
        raise TargetConfigAuditError(f"{path}.constant must be numeric or null")


def _validate_pool_stream(value: Any, path: str) -> str:
    stream = _mapping(value, path)
    mode = stream.get("mode")
    if mode not in ("read", "write"):
        raise TargetConfigAuditError(f"{path}.mode must be read or write")
    if stream.get("target") not in ("A", "B", "B'", "C", "D"):
        raise TargetConfigAuditError(f"{path}.target is unsupported")
    common = {
        "target", "mode", "base_addr", "mem_idx_mode", "mem_idx_keep_last_index",
        "mem_idx_constant", "idx", "idx_size", "dim_stride", "tailing_enable",
        "idx_tailing_range", "address_remapping", "buf_idx_mode",
        "buf_idx_keep_last_index", "buf_spatial_stride", "buf_spatial_size",
        "ping_pong", "pingpong_last_index",
    }
    read_only = {"padding_enable", "padding_reg_value", "idx_padding_range", "buf_full_last_index"}
    _exact_keys(stream, common | (read_only if mode == "read" else set()), path)
    _base_address(stream.get("base_addr"), f"{path}.base_addr")
    for field, length, width in (
        ("idx_size", 3, 8),
        ("dim_stride", 3, 20),
        ("mem_idx_keep_last_index", 3, 4),
        ("buf_idx_keep_last_index", 2, 4),
    ):
        values = stream.get(field)
        if not isinstance(values, list) or len(values) != length:
            raise TargetConfigAuditError(f"{path}.{field} must contain {length} values")
        for index, item in enumerate(values):
            _uint(item, width, f"{path}.{field}[{index}]", nullable=True)
    for field, length, allowed in (
        ("mem_idx_mode", 3, {"buffer", "keep", "constant", None}),
        ("buf_idx_mode", 2, {"buffer", "keep", "constant", None}),
    ):
        values = stream.get(field)
        if not isinstance(values, list) or len(values) != length or any(item not in allowed for item in values):
            raise TargetConfigAuditError(f"{path}.{field} contains unsupported modes")
    for field, length in (("mem_idx_constant", 3), ("idx", 3)):
        values = stream.get(field)
        if not isinstance(values, list) or len(values) != length:
            raise TargetConfigAuditError(f"{path}.{field} must contain {length} values")
        for index, item in enumerate(values):
            if isinstance(item, int) and not isinstance(item, bool):
                _uint(item, 8 if field == "mem_idx_constant" else 5, f"{path}.{field}[{index}]")
    _bits(stream.get("tailing_enable"), 3, f"{path}.tailing_enable")
    if mode == "read":
        _bits(stream.get("padding_enable"), 3, f"{path}.padding_enable")
        _uint(stream.get("padding_reg_value"), 8, f"{path}.padding_reg_value", nullable=True)
        _uint(stream.get("buf_full_last_index"), 4, f"{path}.buf_full_last_index")
        padding_range = _mapping(stream.get("idx_padding_range"), f"{path}.idx_padding_range")
        _exact_keys(padding_range, {"low_bound", "up_bound"}, f"{path}.idx_padding_range")
        for field in ("low_bound", "up_bound"):
            values = padding_range[field]
            if not isinstance(values, list) or len(values) != 3:
                raise TargetConfigAuditError(f"{path}.idx_padding_range.{field} must contain three values")
            for index, item in enumerate(values):
                _uint(item, 12, f"{path}.idx_padding_range.{field}[{index}]", nullable=True)
    tail_range = _mapping(stream.get("idx_tailing_range"), f"{path}.idx_tailing_range")
    _exact_keys(tail_range, {"low", "up"}, f"{path}.idx_tailing_range")
    for field in ("low", "up"):
        values = tail_range[field]
        if not isinstance(values, list) or len(values) != 3:
            raise TargetConfigAuditError(f"{path}.idx_tailing_range.{field} must contain three values")
        for index, item in enumerate(values):
            _uint(item, 12, f"{path}.idx_tailing_range.{field}[{index}]", nullable=True)
    remapping = stream["address_remapping"]
    if remapping is not None and (
        not isinstance(remapping, list)
        or len(remapping) != 26
        or sorted(remapping) != list(range(26))
    ):
        raise TargetConfigAuditError(f"{path}.address_remapping must be null or a permutation of 0..25")
    _uint(stream.get("ping_pong"), 1, f"{path}.ping_pong")
    _uint(stream.get("pingpong_last_index"), 4, f"{path}.pingpong_last_index", nullable=True)
    spatial = stream.get("buf_spatial_stride")
    if not isinstance(spatial, list) or len(spatial) > 16:
        raise TargetConfigAuditError(f"{path}.buf_spatial_stride exceeds 16 entries")
    for index, item in enumerate(spatial):
        _uint(item, 5, f"{path}.buf_spatial_stride[{index}]")
    _uint(stream.get("buf_spatial_size"), 5, f"{path}.buf_spatial_size")
    return mode


def _validate_ga_template(
    config: dict[str, Any],
    *,
    label: str,
    allowed_ga_opcodes: set[str],
) -> dict[str, Any]:
    """Validate a GA template before invoking the wrapping official encoder."""

    expected_top = {
        "CONFIG",
        "dram_loop_configs",
        "lc_pe_configs",
        "buffer_loop_configs",
        "stream_engine",
        "buffer_config",
        "general_array",
    }
    _exact_keys(config, expected_top, f"{label} config")
    mask = config["CONFIG"]
    if not isinstance(mask, str) or len(mask) != 8 or set(mask) - {"0", "1"}:
        raise TargetConfigAuditError("CONFIG must be an eight-bit binary string")

    dram = _resource_keys(config, "dram_loop_configs")
    for name, raw in dram.items():
        path = f"dram_loop_configs.{name}"
        loop = _mapping(raw, path)
        _exact_keys(loop, {"src_id", "outmost_loop", "start", "end", "stride", "last_index"}, path)
        _uint(loop["outmost_loop"], 1, f"{path}.outmost_loop")
        _signed_int(loop["start"], 17, f"{path}.start")
        for field in ("end", "stride"):
            _uint(loop[field], 17, f"{path}.{field}")
        _uint(loop["last_index"], 4, f"{path}.last_index")
        if isinstance(loop["src_id"], int):
            _uint(loop["src_id"], 4, f"{path}.src_id")

    loop_pes = _resource_keys(config, "lc_pe_configs")
    for name, raw in loop_pes.items():
        path = f"lc_pe_configs.{name}"
        pe = _mapping(raw, path)
        _exact_keys(pe, {"alu_opcode", "inport0", "inport1", "inport2"}, path)
        if pe["alu_opcode"] not in ("add", "mul", "mac"):
            raise TargetConfigAuditError(f"{path}.alu_opcode is unsupported")
        for index in range(3):
            _validate_loop_port(
                pe[f"inport{index}"],
                f"{path}.inport{index}",
                src_width=4,
                constant_width=16,
            )

    groups = _resource_keys(config, "buffer_loop_configs")
    for name, raw in groups.items():
        path = f"buffer_loop_configs.{name}"
        group = _mapping(raw, path)
        _exact_keys(group, {"target", "ROW_LC", "COL_LC"}, path)
        for kind, width in (("ROW_LC", 3), ("COL_LC", 6)):
            loop = _mapping(group[kind], f"{path}.{kind}")
            _exact_keys(loop, {"src_id", "start", "end", "stride", "last_index"}, f"{path}.{kind}")
            for field in ("start", "end", "stride"):
                _uint(loop[field], width, f"{path}.{kind}.{field}")
            _uint(loop["last_index"], 4, f"{path}.{kind}.last_index")
            if isinstance(loop["src_id"], int):
                _uint(loop["src_id"], 4, f"{path}.{kind}.src_id")

    streams = _mapping(config["stream_engine"], "stream_engine")
    if len(streams) > 5 or any(re.fullmatch(r"stream\d+", key) is None for key in streams):
        raise TargetConfigAuditError("stream_engine exceeds five valid stream resources")
    modes = [_validate_pool_stream(value, f"stream_engine.{key}") for key, value in streams.items()]
    if modes.count("read") > 4 or modes.count("write") > 1:
        raise TargetConfigAuditError("stream_engine exceeds 4-read/1-write hardware resources")

    buffers = _resource_keys(config, "buffer_config")
    for name, raw in buffers.items():
        path = f"buffer_config.{name}"
        record = _mapping(raw, path)
        required = {"enable", "nbr_enable", "buf_full_last_index", "dst_port", "buffer_life_time", "mode", "mask", "buf_end_row_addr"}
        if not required.issubset(record) or set(record) - (required | {"buffer_nbr_cnt"}):
            raise TargetConfigAuditError(f"{path} fields are invalid")
        for field, width in (("enable", 1), ("nbr_enable", 1), ("buf_full_last_index", 4), ("dst_port", 1), ("buffer_life_time", 4), ("mode", 1), ("buf_end_row_addr", 2)):
            _uint(record[field], width, f"{path}.{field}")
        if record["buffer_life_time"] == 0:
            raise TargetConfigAuditError(f"{path}.buffer_life_time must be at least one")
        _bits(record["mask"], 8, f"{path}.mask")
        if "buffer_nbr_cnt" in record:
            _uint(record["buffer_nbr_cnt"], 5, f"{path}.buffer_nbr_cnt", nullable=True)

    ga = _mapping(config["general_array"], "general_array")
    _exact_keys(ga, {"inport", "outport", "PE_array"}, "general_array")
    inports = _mapping(ga["inport"], "general_array.inport")
    if len(inports) > 3 or any(re.fullmatch(r"inport[0-2]", key) is None for key in inports):
        raise TargetConfigAuditError("general_array.inport exceeds three resources")
    inport_fields = {
        "mask", "src_id", "pingpong_en", "pingpong_last_index", "nbr_enable",
        "fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32",
    }
    for name, raw in inports.items():
        path = f"general_array.inport.{name}"
        record = _mapping(raw, path)
        _exact_keys(record, inport_fields, path)
        _bits(record["mask"], 8, f"{path}.mask")
        _uint(record["src_id"], 1, f"{path}.src_id")
        _uint(record["pingpong_en"], 1, f"{path}.pingpong_en")
        _uint(record["pingpong_last_index"], 4, f"{path}.pingpong_last_index", nullable=True)
        _uint(record["nbr_enable"], 1, f"{path}.nbr_enable")
        for field in ("fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32"):
            if record[field] not in ("true", "false", True, False):
                raise TargetConfigAuditError(f"{path}.{field} must be boolean")
    outport = _mapping(ga["outport"], "general_array.outport")
    _exact_keys(outport, {"mask", "src_id", "fp32tofp16", "fp32tobf16", "int32touint8"}, "general_array.outport")
    _bits(outport["mask"], 8, "general_array.outport.mask")
    _uint(outport["src_id"], 1, "general_array.outport.src_id")
    for field in ("fp32tofp16", "fp32tobf16", "int32touint8"):
        if outport[field] not in ("true", "false", True, False):
            raise TargetConfigAuditError(f"general_array.outport.{field} must be boolean")
    pes = _mapping(ga["PE_array"], "general_array.PE_array")
    if len(pes) > 16 or any(re.fullmatch(r"PE[0-3][0-3]", key) is None for key in pes):
        raise TargetConfigAuditError("general_array.PE_array exceeds the 4x4 array")
    for name, raw in pes.items():
        path = f"general_array.PE_array.{name}"
        pe = _mapping(raw, path)
        _exact_keys(pe, {"alu_opcode", "transout_last_index", "inport0", "inport1", "inport2"}, path)
        if pe.get("alu_opcode") not in allowed_ga_opcodes:
            raise TargetConfigAuditError(
                f"general_array.PE_array.{name} must use one of "
                f"{sorted(allowed_ga_opcodes)}"
            )
        _uint(
            pe.get("transout_last_index"),
            4,
            f"general_array.PE_array.{name}.transout_last_index",
            nullable=True,
        )
        for index in range(3):
            _validate_loop_port(
                pe.get(f"inport{index}"),
                f"general_array.PE_array.{name}.inport{index}",
                src_width=3,
                constant_width=32,
            )

    return {
        "status": "valid",
        "validation_scope": "structure_resources_field_ranges_and_routes_only",
        "config_mask": mask,
        "ga_opcodes": sorted({pe["alu_opcode"] for pe in pes.values()}),
        "resources": {
            "dram_loops": len(dram),
            "loop_pes": len(loop_pes),
            "buffer_loop_groups": len(groups),
            "read_streams": modes.count("read"),
            "write_streams": modes.count("write"),
            "buffers": len(buffers),
            "ga_inports": len(inports),
            "ga_pes": len(pes),
        },
        "field_routes": deepcopy(_FIELD_ROUTES),
    }


def validate_maxpool_template(config: dict[str, Any]) -> dict[str, Any]:
    """Validate an official MaxPool template before encoding."""

    return _validate_ga_template(
        config,
        label="maxpool",
        allowed_ga_opcodes={"int8_max"},
    )


def validate_avgpool_template(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the official AvgPool reduction template before encoding."""

    return _validate_ga_template(
        config,
        label="avgpool",
        allowed_ga_opcodes={"int32_sum"},
    )


def _expect_fields(
    record: dict[str, Any],
    expected: dict[str, Any],
    path: str,
) -> None:
    for field, wanted in expected.items():
        actual = record.get(field)
        if actual != wanted:
            raise TargetConfigAuditError(
                f"{path}.{field}={actual!r}, expected {wanted!r} from Pool linkage"
            )


def _flag(value: Any) -> bool:
    if value in (True, "true"):
        return True
    if value in (False, "false"):
        return False
    raise TargetConfigAuditError(f"invalid boolean flag: {value!r}")


def _expect_port_role(
    port: dict[str, Any],
    *,
    src_id: Any,
    mode: str | None,
    path: str,
) -> None:
    if port.get("src_id") != src_id or port.get("mode") != mode:
        raise TargetConfigAuditError(
            f"{path} source/mode differs from the audited GA topology"
        )


def validate_quant_template(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the INT32-buffer-to-UINT8 GA requant template topology."""

    structural = _validate_ga_template(
        config,
        label="quant_from_buffer",
        allowed_ga_opcodes={"mac", "int32_sub"},
    )
    ga = config["general_array"]
    inports = ga["inport"]
    if set(inports) != {"inport0", "inport1", "inport2"}:
        raise TargetConfigAuditError("quant template must expose three GA inport records")
    for name, record in inports.items():
        conversions = {
            field: _flag(record[field])
            for field in (
                "fp16tofp32",
                "bf16tofp32",
                "int32tofp32",
                "uint8tofp32",
                "uint8toint32",
            )
        }
        expected = {
            "fp16tofp32": False,
            "bf16tofp32": False,
            "int32tofp32": name == "inport0",
            "uint8tofp32": False,
            "uint8toint32": False,
        }
        if conversions != expected:
            raise TargetConfigAuditError(f"quant {name} conversion route differs")
    if inports["inport0"]["mask"] != [1] * 8:
        raise TargetConfigAuditError("quant input lane mask must expose eight INT32 lanes")
    outport = ga["outport"]
    if (
        outport["mask"] != [1] * 8
        or outport["src_id"] != 1
        or _flag(outport["fp32tofp16"])
        or _flag(outport["fp32tobf16"])
        or not _flag(outport["int32touint8"])
    ):
        raise TargetConfigAuditError("quant output route must clamp INT32 to eight UINT8 lanes")

    pes = ga["PE_array"]
    if set(pes) != set(_QUANT_MAC_PES) | set(_QUANT_SUB_PES):
        raise TargetConfigAuditError("quant template must use the audited 8 MAC + 8 INT32_SUB topology")
    for mac_name, sub_name in zip(_QUANT_MAC_PES, _QUANT_SUB_PES, strict=True):
        mac = pes[mac_name]
        sub = pes[sub_name]
        if mac["alu_opcode"] != "mac" or sub["alu_opcode"] != "int32_sub":
            raise TargetConfigAuditError("quant GA opcode pairing differs")
        _expect_port_role(
            mac["inport0"], src_id=0, mode="buffer", path=f"quant.{mac_name}.inport0"
        )
        _expect_port_role(
            mac["inport1"], src_id=None, mode="constant", path=f"quant.{mac_name}.inport1"
        )
        _expect_port_role(
            mac["inport2"], src_id=None, mode="constant", path=f"quant.{mac_name}.inport2"
        )
        _expect_port_role(
            sub["inport0"],
            src_id=f"GA_PE.{mac_name}",
            mode="buffer",
            path=f"quant.{sub_name}.inport0",
        )
        _expect_port_role(
            sub["inport1"], src_id=None, mode="constant", path=f"quant.{sub_name}.inport1"
        )
    return {
        **structural,
        "stage_scope": "int32_input_to_uint8_requant_candidate",
        "ga_topology": "8x(mac_then_int32_sub)",
    }


def validate_add_dequant_template(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the two-branch UINT8-to-FP32 affine-add GA topology."""

    structural = _validate_ga_template(
        config,
        label="add_dequant",
        allowed_ga_opcodes={"mac", "add"},
    )
    ga = config["general_array"]
    inports = ga["inport"]
    active_mask = [1, 0, 1, 0, 1, 0, 1, 0]
    for name in ("inport0", "inport1"):
        record = inports[name]
        if record["mask"] != active_mask or not _flag(record["uint8tofp32"]):
            raise TargetConfigAuditError(f"add-dequant {name} must convert four UINT8 lanes to FP32")
        if any(
            _flag(record[field])
            for field in ("fp16tofp32", "bf16tofp32", "int32tofp32", "uint8toint32")
        ):
            raise TargetConfigAuditError(f"add-dequant {name} enables an unexpected conversion")
    outport = ga["outport"]
    if (
        outport["mask"] != [0, 1, 0, 1, 0, 1, 0, 1]
        or outport["src_id"] != 0
        or any(
            _flag(outport[field])
            for field in ("fp32tofp16", "fp32tobf16", "int32touint8")
        )
    ):
        raise TargetConfigAuditError("add-dequant output route must remain FP32")

    pes = ga["PE_array"]
    expected_pes = set(_ADD_DEQUANT_A_PES) | set(_ADD_DEQUANT_B_PES) | set(_ADD_DEQUANT_SUM_PES)
    if set(pes) != expected_pes:
        raise TargetConfigAuditError("add-dequant template must use the audited 8 MAC + 4 ADD topology")
    for name in _ADD_DEQUANT_A_PES:
        pe = pes[name]
        if pe["alu_opcode"] != "mac":
            raise TargetConfigAuditError(f"add-dequant {name} must be MAC")
        _expect_port_role(pe["inport0"], src_id=0, mode="buffer", path=f"add_dequant.{name}.inport0")
        _expect_port_role(pe["inport1"], src_id=None, mode="constant", path=f"add_dequant.{name}.inport1")
        _expect_port_role(pe["inport2"], src_id=None, mode="constant", path=f"add_dequant.{name}.inport2")
    for name in _ADD_DEQUANT_B_PES:
        pe = pes[name]
        if pe["alu_opcode"] != "mac":
            raise TargetConfigAuditError(f"add-dequant {name} must be MAC")
        _expect_port_role(pe["inport0"], src_id=None, mode="constant", path=f"add_dequant.{name}.inport0")
        _expect_port_role(pe["inport1"], src_id=0, mode="buffer", path=f"add_dequant.{name}.inport1")
        _expect_port_role(pe["inport2"], src_id=None, mode="constant", path=f"add_dequant.{name}.inport2")
    sum_sources = {
        "PE10": ("GA_PE.PE01", "GA_PE.PE00"),
        "PE12": ("GA_PE.PE03", "GA_PE.PE02"),
        "PE30": ("GA_PE.PE21", "GA_PE.PE20"),
        "PE32": ("GA_PE.PE23", "GA_PE.PE22"),
    }
    for name, sources in sum_sources.items():
        pe = pes[name]
        if pe["alu_opcode"] != "add":
            raise TargetConfigAuditError(f"add-dequant {name} must be ADD")
        for index, source in enumerate(sources):
            _expect_port_role(
                pe[f"inport{index}"],
                src_id=source,
                mode="buffer",
                path=f"add_dequant.{name}.inport{index}",
            )
    return {
        **structural,
        "stage_scope": "two_uint8_inputs_to_fp32_affine_sum_only",
        "ga_topology": "4x(two_branch_mac_then_add)",
    }


def _active_ga_pe_names(config: dict[str, Any]) -> list[str]:
    return sorted(config["general_array"]["PE_array"])


def validate_maxpool_shape_linkage(
    config: dict[str, Any],
    *,
    channels: int,
    height: int,
    width: int,
    kernel: int = 3,
    stride: int = 2,
    padding: int = 1,
) -> dict[str, Any]:
    """Validate the exact shape linkage shared by the two official MaxPool templates.

    The two checked templates cover square, channel-16, non-tail shapes only.  This
    function deliberately rejects shapes outside that evidence instead of guessing
    a new tiling rule.
    """

    structural = validate_maxpool_template(config)
    if (
        channels <= 0
        or height <= 0
        or width <= 0
        or channels % 4
        or height % stride
        or width % 16
        or kernel != 3
        or stride != 2
        or padding != 1
    ):
        raise TargetConfigAuditError(
            "official MaxPool linkage only covers C%4=0, H%2=0, W%16=0, "
            "kernel=3, stride=2, padding=1"
        )
    output_h = (height + 2 * padding - kernel) // stride + 1
    output_w = (width + 2 * padding - kernel) // stride + 1
    if output_w % 8:
        raise TargetConfigAuditError("official MaxPool write tile requires output width divisible by 8")

    dram = config["dram_loop_configs"]
    expected_dram = {
        "LC0": {"src_id": None, "outmost_loop": 1, "start": 0, "end": channels // 4, "stride": 1, "last_index": 0},
        "LC1": {"src_id": "DRAM_LC.LC0", "outmost_loop": 0, "start": 0, "end": height, "stride": stride, "last_index": 1},
        "LC2": {"src_id": "DRAM_LC.LC1", "outmost_loop": 0, "start": 0, "end": width // 16, "stride": 1, "last_index": 2},
        "LC3": {"src_id": "DRAM_LC.LC2", "outmost_loop": 0, "start": 0, "end": kernel, "stride": 1, "last_index": 3},
        "LC4": {"src_id": "DRAM_LC.LC3", "outmost_loop": 0, "start": 0, "end": kernel, "stride": 1, "last_index": 4},
        "LC5": {"src_id": "DRAM_LC.LC4", "outmost_loop": 0, "start": 0, "end": 16, "stride": stride, "last_index": 5},
        "LC6": {"src_id": "DRAM_LC.LC0", "outmost_loop": 0, "start": 0, "end": output_h, "stride": 1, "last_index": 1},
        "LC7": {"src_id": "DRAM_LC.LC6", "outmost_loop": 0, "start": 0, "end": output_w // 8, "stride": 1, "last_index": 2},
    }
    if set(dram) != set(expected_dram):
        raise TargetConfigAuditError("MaxPool DRAM LC set differs from the two-template rule")
    for name, expected in expected_dram.items():
        _expect_fields(dram[name], expected, f"dram_loop_configs.{name}")

    loop_pes = config["lc_pe_configs"]
    index_links = {
        "PE0": ("mac", "DRAM_LC.LC1", 1, "DRAM_LC.LC3"),
        "PE1": ("mac", "DRAM_LC.LC2", 16, "DRAM_LC.LC4"),
        "PE2": ("mac", "LC_PE.PE1", 1, "DRAM_LC.LC5"),
    }
    for name, (opcode, in0, multiplier, in2) in index_links.items():
        pe = loop_pes[name]
        if (
            pe["alu_opcode"] != opcode
            or pe["inport0"]["src_id"] != in0
            or pe["inport1"]["mode"] != "constant"
            or pe["inport1"]["constant"] != multiplier
            or pe["inport2"]["src_id"] != in2
        ):
            raise TargetConfigAuditError(f"lc_pe_configs.{name} breaks the MaxPool affine index chain")

    width_tiles = width // 16
    collapsed_width_tile = width_tiles == 1
    a_row_source = "DRAM_LC.LC4" if collapsed_width_tile else "DRAM_LC.LC5"
    a_row_last = 5 if collapsed_width_tile else 6
    a_col_last = a_row_last + 1
    groups = config["buffer_loop_configs"]
    _expect_fields(groups["GROUP0"], {"target": "A"}, "buffer_loop_configs.GROUP0")
    _expect_fields(
        groups["GROUP0"]["ROW_LC"],
        {"src_id": a_row_source, "start": 0, "end": 1, "stride": 1, "last_index": a_row_last},
        "buffer_loop_configs.GROUP0.ROW_LC",
    )
    _expect_fields(
        groups["GROUP0"]["COL_LC"],
        {"src_id": "GROUP0.ROW_LC", "start": 0, "end": 32, "stride": 4, "last_index": a_col_last},
        "buffer_loop_configs.GROUP0.COL_LC",
    )
    _expect_fields(groups["GROUP1"], {"target": "D"}, "buffer_loop_configs.GROUP1")
    _expect_fields(
        groups["GROUP1"]["ROW_LC"],
        {"src_id": "DRAM_LC.LC7", "start": 0, "end": 1, "stride": 1, "last_index": 3},
        "buffer_loop_configs.GROUP1.ROW_LC",
    )
    _expect_fields(
        groups["GROUP1"]["COL_LC"],
        {"src_id": "GROUP1.ROW_LC", "start": 0, "end": 32, "stride": 16, "last_index": 4},
        "buffer_loop_configs.GROUP1.COL_LC",
    )

    read = config["stream_engine"]["stream0"]
    write = config["stream_engine"]["stream1"]
    _expect_fields(
        read,
        {
            "target": "A",
            "mode": "read",
            "idx": ["LC_PE.PE2", "LC_PE.PE0", "LC_PE.PE3"],
            "idx_size": [0, 0, 3],
            "dim_stride": [4, 4 * width, 4 * height * width],
            "padding_enable": [1, 1, 0],
            "buf_idx_keep_last_index": [a_col_last, 7],
            "buf_spatial_stride": [0, 1, 2, 3],
            "buf_spatial_size": 4,
            "buf_full_last_index": a_row_last,
        },
        "stream_engine.stream0",
    )
    _expect_fields(
        read["idx_padding_range"],
        {"low_bound": [padding, padding, None], "up_bound": [width, height, None]},
        "stream_engine.stream0.idx_padding_range",
    )
    _expect_fields(
        write,
        {
            "target": "D",
            "mode": "write",
            "idx": ["LC_PE.PE5", "DRAM_LC.LC6", "DRAM_LC.LC7"],
            "idx_size": [3, 0, 7],
            "dim_stride": [4 * output_h * output_w, 4 * output_w, 32],
            "buf_idx_keep_last_index": [4, 7],
            "buf_spatial_stride": list(range(16)),
            "buf_spatial_size": 16,
        },
        "stream_engine.stream1",
    )
    _expect_fields(
        config["buffer_config"]["buffer0"],
        {"enable": 1, "dst_port": 1, "buf_full_last_index": a_row_last, "buffer_life_time": 1, "mask": [1] * 8},
        "buffer_config.buffer0",
    )
    _expect_fields(
        config["buffer_config"]["buffer5"],
        {"enable": 1, "dst_port": 1, "buf_full_last_index": 3, "buffer_life_time": 1, "mask": [1] * 8},
        "buffer_config.buffer5",
    )

    expected_ga_pes = ["PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32"]
    if _active_ga_pe_names(config) != expected_ga_pes:
        raise TargetConfigAuditError("MaxPool GA lane placement differs from the official templates")
    for name, pe in config["general_array"]["PE_array"].items():
        _expect_fields(pe, {"alu_opcode": "int8_max", "transout_last_index": 3}, f"general_array.PE_array.{name}")
    _expect_fields(
        config["general_array"]["inport"]["inport0"],
        {"mask": [1] * 8, "src_id": 0, "uint8toint32": "false"},
        "general_array.inport.inport0",
    )

    return {
        "status": "passed",
        "rule_strength": "exact_for_two_official_non_tail_templates",
        "shape": {
            "channels": channels,
            "height": height,
            "width": width,
            "kernel": kernel,
            "stride": stride,
            "padding": padding,
            "output_height": output_h,
            "output_width": output_w,
        },
        "lc_formulas": {
            "channel_groups": "LC0.end=C/4",
            "input_row_starts": "LC1=[0,H) step 2",
            "input_width_tiles": "LC2.end=W/16",
            "kernel_rows_and_cols": "LC3.end=LC4.end=3",
            "tile_output_columns": "LC5=[0,16) step 2",
            "output_rows": "LC6.end=Hout",
            "output_width_tiles": "LC7.end=Wout/8",
        },
        "affine_indices": {
            "input_row": "LC1 + LC3",
            "input_col": "LC2*16 + LC4 + LC5",
            "input_channel_group": "LC0",
        },
        "stream_formulas": {
            "read_dim_stride_bytes": [4, 4 * width, 4 * height * width],
            "write_dim_stride_bytes": [4 * output_h * output_w, 4 * output_w, 32],
            "padding_valid_inclusive": [[padding, width], [padding, height], None],
        },
        "buffer_schedule": {
            "collapsed_single_width_tile": collapsed_width_tile,
            "a_row_source": a_row_source,
            "a_buffer_full_last_index": a_row_last,
            "a_col_last_index": a_col_last,
        },
        "ga": {
            "active_pes": expected_ga_pes,
            "opcode": "int8_max",
            "transout_last_index": 3,
            "uint8toint32": False,
        },
        "base_addresses": {
            "read": _base_address(read["base_addr"], "stream_engine.stream0.base_addr"),
            "write": _base_address(write["base_addr"], "stream_engine.stream1.base_addr"),
            "rule": "planner_owned_and_not_inferred_from_shape",
        },
        "structural_validation": structural,
        "not_proven": [
            "uint8 numerical comparison semantics of the symbolic int8_max opcode",
            "tail or non-divisible width scheduling",
            "target simulator or hardware numerical output",
        ],
    }


def validate_avgpool_shape_linkage(
    config: dict[str, Any],
    *,
    channels: int,
    height: int,
    width: int,
) -> dict[str, Any]:
    """Validate the exact reduction linkage in the one official AvgPool template."""

    structural = validate_avgpool_template(config)
    if channels <= 0 or height <= 0 or width <= 0 or channels % 8:
        raise TargetConfigAuditError("official AvgPool linkage requires positive C/H/W and C%8=0")
    reduction = height * width
    padded_reduction = ((reduction + 7) // 8) * 8

    dram = config["dram_loop_configs"]
    expected_dram = {
        "LC0": {"src_id": None, "outmost_loop": 1, "start": 0, "end": channels // 8, "stride": 1, "last_index": 0},
        "LC1": {"src_id": "DRAM_LC.LC0", "outmost_loop": 0, "start": 0, "end": padded_reduction, "stride": 4, "last_index": 1},
        "LC2": {"src_id": "DRAM_LC.LC0", "outmost_loop": 0, "start": 0, "end": 1, "stride": 1, "last_index": 1},
    }
    if set(dram) != set(expected_dram):
        raise TargetConfigAuditError("AvgPool DRAM LC set differs from the official reduction template")
    for name, expected in expected_dram.items():
        _expect_fields(dram[name], expected, f"dram_loop_configs.{name}")

    loop_pes = config["lc_pe_configs"]
    for name, source in (("PE0", "DRAM_LC.LC0"), ("PE1", "DRAM_LC.LC2")):
        pe = loop_pes[name]
        if (
            pe["alu_opcode"] != "mul"
            or pe["inport0"]["src_id"] != source
            or pe["inport1"]["mode"] != "constant"
            or pe["inport1"]["constant"] != 1
        ):
            raise TargetConfigAuditError(f"lc_pe_configs.{name} breaks the AvgPool index pass-through")

    read = config["stream_engine"]["stream0"]
    write = config["stream_engine"]["stream1"]
    _expect_fields(
        read,
        {
            "target": "A",
            "mode": "read",
            "idx": ["LC_PE.PE0", "DRAM_LC.LC1", None],
            "idx_size": [7, 3, None],
            "dim_stride": [reduction * 8, 8, None],
            "padding_enable": [0, 1, 0],
            "buf_idx_keep_last_index": [3, 7],
            "buf_spatial_stride": [0, 4, 8, 12, 16, 20, 24, 28, 1, 5, 9, 13, 17, 21, 25, 29],
            "buf_spatial_size": 16,
            "buf_full_last_index": 2,
        },
        "stream_engine.stream0",
    )
    _expect_fields(
        read["idx_padding_range"],
        {"low_bound": [None, 0, None], "up_bound": [None, reduction - 1, None]},
        "stream_engine.stream0.idx_padding_range",
    )
    _expect_fields(
        write,
        {
            "target": "D",
            "mode": "write",
            "idx": ["LC_PE.PE1", None, None],
            "idx_size": [31, None, None],
            "dim_stride": [32, None, None],
            "buf_idx_keep_last_index": [3, 7],
            "buf_spatial_stride": list(range(16)),
            "buf_spatial_size": 16,
        },
        "stream_engine.stream1",
    )

    groups = config["buffer_loop_configs"]
    expected_groups = {
        "GROUP0": {
            "target": "A",
            "row": {"src_id": "DRAM_LC.LC1", "start": 0, "end": 1, "stride": 1, "last_index": 2},
            "col": {"src_id": "GROUP0.ROW_LC", "start": 0, "end": 4, "stride": 2, "last_index": 3},
        },
        "GROUP1": {
            "target": "D",
            "row": {"src_id": "DRAM_LC.LC2", "start": 0, "end": 1, "stride": 1, "last_index": 2},
            "col": {"src_id": "GROUP1.ROW_LC", "start": 0, "end": 32, "stride": 16, "last_index": 3},
        },
    }
    for name, expected in expected_groups.items():
        _expect_fields(groups[name], {"target": expected["target"]}, f"buffer_loop_configs.{name}")
        _expect_fields(groups[name]["ROW_LC"], expected["row"], f"buffer_loop_configs.{name}.ROW_LC")
        _expect_fields(groups[name]["COL_LC"], expected["col"], f"buffer_loop_configs.{name}.COL_LC")
    for name in ("buffer0", "buffer5"):
        _expect_fields(
            config["buffer_config"][name],
            {"enable": 1, "dst_port": 1, "buf_full_last_index": 2, "buffer_life_time": 1, "mask": [1] * 8},
            f"buffer_config.{name}",
        )

    expected_ga_pes = ["PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32"]
    if _active_ga_pe_names(config) != expected_ga_pes:
        raise TargetConfigAuditError("AvgPool GA lane placement differs from the official template")
    for name, pe in config["general_array"]["PE_array"].items():
        _expect_fields(pe, {"alu_opcode": "int32_sum", "transout_last_index": 1}, f"general_array.PE_array.{name}")
    _expect_fields(
        config["general_array"]["inport"]["inport0"],
        {"mask": [1] * 8, "src_id": 0, "uint8toint32": "true"},
        "general_array.inport.inport0",
    )
    _expect_fields(
        config["general_array"]["outport"],
        {"mask": [1] * 8, "src_id": 0, "int32touint8": "false"},
        "general_array.outport",
    )

    return {
        "status": "passed",
        "rule_strength": "exact_for_one_official_shape_candidate_for_generalization",
        "stage_scope": "uint8_input_to_int32_spatial_sum_only",
        "shape": {
            "channels": channels,
            "height": height,
            "width": width,
            "reduction_elements": reduction,
            "padded_reduction_elements": padded_reduction,
            "output_shape": [channels, 1, 1],
        },
        "lc_formulas": {
            "channel_groups": "LC0.end=C/8",
            "spatial_reduction": "LC1.end=round_up(H*W,8), stride=4",
            "output_event": "LC2.end=1 under LC0",
        },
        "stream_formulas": {
            "read_transaction_elements_minus_one": [7, 3, None],
            "read_dim_stride_bytes": [reduction * 8, 8, None],
            "padding_valid_inclusive": [None, [0, reduction - 1], None],
            "write_transaction_elements_minus_one": [31, None, None],
            "write_dim_stride_bytes": [32, None, None],
        },
        "buffer_schedule": {
            "read_and_write_buffer_full_last_index": 2,
            "read_spatial_lane_map": read["buf_spatial_stride"],
            "write_spatial_lane_map": write["buf_spatial_stride"],
        },
        "ga": {
            "active_pes": expected_ga_pes,
            "input_conversion": "uint8_to_int32",
            "opcode": "int32_sum",
            "transout_last_index": 1,
            "output_conversion": "none",
        },
        "base_addresses": {
            "read": _base_address(read["base_addr"], "stream_engine.stream0.base_addr"),
            "write": _base_address(write["base_addr"], "stream_engine.stream1.base_addr"),
            "rule": "planner_owned_and_not_inferred_from_shape",
        },
        "structural_validation": structural,
        "not_proven": [
            "AvgPool division by H*W",
            "x_scale/y_scale requantization",
            "rounding and uint8 saturation",
            "other H/W shapes or tail policies",
            "target simulator or hardware numerical output",
        ],
    }


def _flatten_leaves(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            result.update(_flatten_leaves(child, child_path))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(_flatten_leaves(child, f"{path}[{index}]"))
        return result
    return {path: value}


def extract_pool_family_linkage(
    first_maxpool: dict[str, Any],
    second_maxpool: dict[str, Any],
    avgpool: dict[str, Any],
) -> dict[str, Any]:
    """Extract evidence-bounded Pool rules without claiming numerical completion."""

    first_linkage = validate_maxpool_shape_linkage(
        first_maxpool, channels=16, height=112, width=112
    )
    second_linkage = validate_maxpool_shape_linkage(
        second_maxpool, channels=16, height=16, width=16
    )
    avg_linkage = validate_avgpool_shape_linkage(
        avgpool, channels=2048, height=7, width=7
    )

    first_leaves = _flatten_leaves(first_maxpool)
    second_leaves = _flatten_leaves(second_maxpool)
    changed_paths = sorted(
        path
        for path in set(first_leaves) | set(second_leaves)
        if first_leaves.get(path) != second_leaves.get(path)
    )
    planner_owned = [
        "stream_engine.stream0.base_addr",
        "stream_engine.stream1.base_addr",
    ]
    expected_shape_linked = sorted(
        {
            "buffer_config.buffer0.buf_full_last_index",
            "buffer_loop_configs.GROUP0.COL_LC.last_index",
            "buffer_loop_configs.GROUP0.ROW_LC.last_index",
            "buffer_loop_configs.GROUP0.ROW_LC.src_id",
            "dram_loop_configs.LC1.end",
            "dram_loop_configs.LC2.end",
            "dram_loop_configs.LC6.end",
            "dram_loop_configs.LC7.end",
            "stream_engine.stream0.buf_full_last_index",
            "stream_engine.stream0.buf_idx_keep_last_index[0]",
            "stream_engine.stream0.dim_stride[1]",
            "stream_engine.stream0.dim_stride[2]",
            "stream_engine.stream0.idx_padding_range.up_bound[0]",
            "stream_engine.stream0.idx_padding_range.up_bound[1]",
            "stream_engine.stream1.dim_stride[0]",
            "stream_engine.stream1.dim_stride[1]",
        }
    )
    actual_shape_linked = sorted(set(changed_paths) - set(planner_owned))
    if actual_shape_linked != expected_shape_linked:
        raise TargetConfigAuditError(
            "MaxPool template delta contains an unexplained shape-linked field: "
            f"actual={actual_shape_linked}, expected={expected_shape_linked}"
        )

    top_groups = sorted(first_maxpool)
    if sorted(second_maxpool) != top_groups or sorted(avgpool) != top_groups:
        raise TargetConfigAuditError("Pool templates do not share one top-level configuration chain")

    return {
        "status": "passed",
        "rule_scope": "three_official_static_templates_at_locked_commit",
        "shared_top_level_groups": top_groups,
        "shared_chain": [
            {
                "stage": "shape",
                "drives": "logical extents, reduction length, tiling, padding and output shape",
            },
            {
                "stage": "LC",
                "drives": "nested loop extents, affine LC-PE indices and completion-event last_index values",
            },
            {
                "stage": "stream",
                "drives": "transaction sizes, byte strides, inclusive valid ranges and buffer lane expansion",
            },
            {
                "stage": "buffer",
                "drives": "A/D row-column coordinates, full events, lifetime, destination and lane masks",
            },
            {
                "stage": "GA",
                "drives": "lane placement, dtype conversion, reduction opcode and output event",
            },
        ],
        "cross_stage_invariants": [
            "stream target A/D matches buffer-loop target and buffer destination GA",
            "stream buf_full_last_index and buffer0 buf_full_last_index name the same LC completion event",
            "buffer and GA masks expose the same eight active 32-bit lanes",
            "all stream strides are byte strides and transaction sizes are encoded as dimension minus one",
            "base addresses belong to the memory planner and are not shape formulas",
        ],
        "maxpool_template_delta": {
            "status": "fully_explained",
            "changed_leaf_count": len(changed_paths),
            "shape_linked_paths": expected_shape_linked,
            "planner_owned_paths": planner_owned,
            "unexpected_paths": [],
        },
        "templates": {
            MAXPOOL_TEMPLATE: first_linkage,
            SECOND_MAXPOOL_TEMPLATE: second_linkage,
            AVGPOOL_TEMPLATE: avg_linkage,
        },
        "limits": [
            "MaxPool formulas are exact only for the two covered non-tail templates",
            "AvgPool shape formula is inferred from one template and must be tested on another shape before parameterization",
            "AvgPool JSON stops at int32 sum; it is not a complete QLinearGlobalAveragePool",
            "static encoding and mapping do not prove numerical simulator or hardware behavior",
        ],
    }


def _fp32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def quant_requant_constant_patch(
    *,
    multiplier: float,
    output_zero_point: int,
) -> dict[str, float | int]:
    """Return semantic constant patches without emitting a W5 JSON instance."""

    if not math.isfinite(multiplier) or multiplier <= 0:
        raise TargetConfigAuditError("requant multiplier must be finite and positive")
    _uint(output_zero_point, 8, "output_zero_point")
    multiplier_fp32 = _fp32(multiplier)
    magic_addend = _fp32(_FP32_ROUND_MAGIC + output_zero_point)
    patch: dict[str, float | int] = {}
    for mac_name, sub_name in zip(_QUANT_MAC_PES, _QUANT_SUB_PES, strict=True):
        patch[f"general_array.PE_array.{mac_name}.inport1.constant"] = multiplier_fp32
        patch[f"general_array.PE_array.{mac_name}.inport2.constant"] = magic_addend
        patch[f"general_array.PE_array.{sub_name}.inport1.constant"] = _FP32_ROUND_MAGIC_BITS
    return patch


def add_dequant_constant_patch(
    *,
    a_scale: float,
    a_zero_point: int,
    b_scale: float,
    b_zero_point: int,
) -> dict[str, float | int]:
    """Return patches for `(A-zA)*sA + (B-zB)*sB` with FP32 output."""

    for name, scale in (("a_scale", a_scale), ("b_scale", b_scale)):
        if not math.isfinite(scale) or scale <= 0:
            raise TargetConfigAuditError(f"{name} must be finite and positive")
    _uint(a_zero_point, 8, "a_zero_point")
    _uint(b_zero_point, 8, "b_zero_point")
    a_scale_fp32 = _fp32(a_scale)
    b_scale_fp32 = _fp32(b_scale)
    a_offset_fp32 = _fp32(-a_zero_point * a_scale_fp32)
    b_offset_fp32 = _fp32(-b_zero_point * b_scale_fp32)
    patch: dict[str, float | int] = {}
    for name in _ADD_DEQUANT_A_PES:
        patch[f"general_array.PE_array.{name}.inport1.constant"] = a_scale_fp32
        patch[f"general_array.PE_array.{name}.inport2.constant"] = a_offset_fp32
    for name in _ADD_DEQUANT_B_PES:
        patch[f"general_array.PE_array.{name}.inport0.constant"] = b_scale_fp32
        patch[f"general_array.PE_array.{name}.inport2.constant"] = b_offset_fp32
    return patch


def extract_ga_quant_add_crosswalk(
    quant: dict[str, Any],
    add_dequant: dict[str, Any],
) -> dict[str, Any]:
    """Extract the evidence-bounded dtype, constant, and qparam GA crosswalk."""

    quant_structural = validate_quant_template(quant)
    add_structural = validate_add_dequant_template(add_dequant)
    quant_pes = quant["general_array"]["PE_array"]
    multipliers = {quant_pes[name]["inport1"]["constant"] for name in _QUANT_MAC_PES}
    addends = {quant_pes[name]["inport2"]["constant"] for name in _QUANT_MAC_PES}
    subtracts = {quant_pes[name]["inport1"]["constant"] for name in _QUANT_SUB_PES}
    if len(multipliers) != 1 or len(addends) != 1 or subtracts != {_FP32_ROUND_MAGIC_BITS}:
        raise TargetConfigAuditError("quant template lanes do not share one audited constant recipe")
    multiplier = float(next(iter(multipliers)))
    addend_literal = float(next(iter(addends)))
    addend_encoded_bits = _fp32_bits(addend_literal)
    addend_encoded_value = struct.unpack("<f", struct.pack("<I", addend_encoded_bits))[0]
    output_zero_point = int(addend_encoded_value - _FP32_ROUND_MAGIC)
    if not 0 <= output_zero_point <= 255:
        raise TargetConfigAuditError("quant magic addend does not encode a UINT8 zero point")

    add_pes = add_dequant["general_array"]["PE_array"]
    a_scales = {add_pes[name]["inport1"]["constant"] for name in _ADD_DEQUANT_A_PES}
    a_offsets = {add_pes[name]["inport2"]["constant"] for name in _ADD_DEQUANT_A_PES}
    b_scales = {add_pes[name]["inport0"]["constant"] for name in _ADD_DEQUANT_B_PES}
    b_offsets = {add_pes[name]["inport2"]["constant"] for name in _ADD_DEQUANT_B_PES}
    if any(len(values) != 1 for values in (a_scales, a_offsets, b_scales, b_offsets)):
        raise TargetConfigAuditError("add-dequant branch constants differ between lanes")
    a_scale = float(next(iter(a_scales)))
    a_offset = float(next(iter(a_offsets)))
    b_scale = float(next(iter(b_scales)))
    b_offset = float(next(iter(b_offsets)))

    return {
        "status": "passed",
        "rule_scope": "two_official_static_ga_templates_at_locked_commit",
        "shared_chain": ["shape", "LC", "stream", "buffer", "GA"],
        "quant_from_buffer": {
            "structural_validation": quant_structural,
            "declared_dtype_path": ["int32_buffer", "fp32_mac", "int32_sub", "uint8_D"],
            "fixed_constants": {
                "multiplier_literal": multiplier,
                "multiplier_fp32_bits": f"0x{_fp32_bits(multiplier):08x}",
                "magic_addend_literal": addend_literal,
                "magic_addend_encoded_fp32": addend_encoded_value,
                "magic_addend_fp32_bits": f"0x{addend_encoded_bits:08x}",
                "magic_subtract_raw_int32": _FP32_ROUND_MAGIC_BITS,
                "magic_subtract_hex": f"0x{_FP32_ROUND_MAGIC_BITS:08x}",
                "derived_output_zero_point": output_zero_point,
            },
            "inferred_recipe": "clamp_uint8(round_fp32_even(int32_input*multiplier)+output_zero_point)",
            "rounding": {
                "status": "recipe_identified_but_not_target_executed",
                "intended_mode": "nearest_even_via_fp32_magic_add_and_raw_int32_subtract",
                "caveat": "bit pattern proves the compiler recipe; target GA FP32 execution has no numerical replay in the available toolchain",
            },
            "saturation": {
                "status": "rtl_static_semantics_identified",
                "rule": "negative_to_0; any_bit_30_through_8_to_255; otherwise_low_8_bits",
                "evidence": "contracts/rtl28_candidate_audit.json:EV_GA_CLAMP",
            },
            "formal_qparam_patch": {
                "multiplier": "patch all eight MAC inport1 constants as fp32",
                "output_zero_point": "encode as fp32(12582912 + y_zero_point) in all eight MAC inport2 constants",
                "round_magic": "keep all eight INT32_SUB inport1 constants fixed at raw 0x4b400000",
                "transport": "per-operator or per-output-channel-tile constant patch followed by official encoding",
            },
            "direct_onnx_quantize_linear_compatible": False,
            "compatibility_reason": "template input is INT32 and consumes a requant multiplier; ONNX QuantizeLinear input is FP32 and consumes 1/y_scale",
        },
        "add_dequant": {
            "structural_validation": add_structural,
            "declared_dtype_path": ["uint8_A", "uint8_B", "two_fp32_affine_branches", "fp32_add", "fp32_D"],
            "fixed_constants": {
                "a_scale": a_scale,
                "a_offset": a_offset,
                "b_scale": b_scale,
                "b_offset": b_offset,
            },
            "static_formula": f"(A*{a_scale}+{a_offset}) + (B*{b_scale}+{b_offset})",
            "formal_fp32_formula": "(A-a_zero_point)*a_scale + (B-b_zero_point)*b_scale",
            "formal_qparam_patch": {
                "a_scale": "patch A-branch MAC multiplier constants",
                "a_zero_point": "derive A-branch offset=-a_zero_point*a_scale",
                "b_scale": "patch B-branch MAC multiplier constants",
                "b_zero_point": "derive B-branch offset=-b_zero_point*b_scale",
                "y_scale_and_y_zero_point": "not consumed because this template writes FP32",
            },
            "rounding": "none_in_template",
            "saturation": "none_in_template",
            "output_dtype": "fp32",
            "complete_qlinearadd_compatible": False,
            "compatibility_reason": "QLinearAdd requires y_scale/y_zero_point, nearest-even and UINT8 saturation; all are absent",
        },
        "formal_configuration_rule": {
            "source_of_truth": "locked ONNX scalar initializers carried by an extended execution-plan operator schema",
            "derivation": "derive constants from named qparams, validate fp32 encoding and lane replication, then patch an isolated template copy",
            "forbidden": [
                "reuse static sample constants as ResNet defaults",
                "place floating-point qparams in the current integer-only/absent OperatorSpec params",
                "treat successful bitstream encoding as numerical validation",
            ],
        },
        "limits": [
            "no target numerical simulator output",
            "no hardware output",
            "quant rounding recipe still requires target execution confirmation",
            "add-dequant is not a complete QLinearAdd or QLinearAdd-plus-Dequantize fusion",
        ],
    }


def audit_resnet_scalar_qparams(
    model_path: Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    """Read only scalar ONNX initializers; never load W3 tensor payloads."""

    if sha256_file(model_path) != expected_sha256:
        raise TargetConfigAuditError("reference ONNX hash differs from the W3 model graph")
    try:
        import onnx
        from onnx import numpy_helper
    except ImportError as error:
        raise TargetConfigAuditError("onnx is required to audit formal scalar qparams") from error

    model = onnx.load(model_path, load_external_data=False)
    initializers = {
        initializer.name: numpy_helper.to_array(initializer)
        for initializer in model.graph.initializer
    }
    positions = {
        "QuantizeLinear": {"y_scale": 1, "y_zero_point": 2},
        "DequantizeLinear": {"x_scale": 1, "x_zero_point": 2},
        "QLinearAdd": {
            "a_scale": 1,
            "a_zero_point": 2,
            "b_scale": 4,
            "b_zero_point": 5,
            "y_scale": 6,
            "y_zero_point": 7,
        },
    }
    records: list[dict[str, Any]] = []
    for index, node in enumerate(model.graph.node):
        if node.op_type not in positions:
            continue
        qparams: dict[str, Any] = {}
        qparam_sources: dict[str, str] = {}
        for field, input_index in positions[node.op_type].items():
            source = node.input[input_index]
            if source not in initializers or initializers[source].size != 1:
                raise TargetConfigAuditError(
                    f"{node.name}.{field} must be a scalar initializer"
                )
            value = initializers[source].reshape(-1)[0]
            qparams[field] = float(value) if "scale" in field else int(value)
            qparam_sources[field] = source
        if any(
            not math.isfinite(value) or value <= 0
            for field, value in qparams.items()
            if "scale" in field
        ):
            raise TargetConfigAuditError(f"{node.name} contains an invalid scale")
        for field, value in qparams.items():
            if "zero_point" in field:
                _uint(value, 8, f"{node.name}.{field}")
        records.append(
            {
                "graph_index": index,
                "name": node.name,
                "op_type": node.op_type,
                "qparams": qparams,
                "qparam_sources": qparam_sources,
            }
        )

    counts = {
        op_type: sum(record["op_type"] == op_type for record in records)
        for op_type in positions
    }
    if counts != {"QuantizeLinear": 2, "DequantizeLinear": 2, "QLinearAdd": 17}:
        raise TargetConfigAuditError(f"formal ResNet qparam operator counts differ: {counts}")
    scales = [
        value
        for record in records
        for field, value in record["qparams"].items()
        if "scale" in field
    ]
    zero_points = [
        value
        for record in records
        for field, value in record["qparams"].items()
        if "zero_point" in field
    ]
    quant_records = [record for record in records if record["op_type"] == "QuantizeLinear"]
    dequant_records = [
        record for record in records if record["op_type"] == "DequantizeLinear"
    ]
    add_records = [record for record in records if record["op_type"] == "QLinearAdd"]
    add_branch_matches = sum(
        scale == 1.0 and _fp32(-zero_point * scale) == 1.0
        for record in add_records
        for scale, zero_point in (
            (record["qparams"]["a_scale"], record["qparams"]["a_zero_point"]),
            (record["qparams"]["b_scale"], record["qparams"]["b_zero_point"]),
        )
    )
    return {
        "status": "passed",
        "source": {
            "path": "artifacts/reference_model/resnet50-v1-12-int8.onnx",
            "sha256": expected_sha256,
            "read_scope": "ONNX scalar initializers only; no W3 NPY payloads",
        },
        "operator_counts": counts,
        "scale_range": [min(scales), max(scales)],
        "zero_point_range": [min(zero_points), max(zero_points)],
        "records": records,
        "static_template_comparison": {
            "quant_template_multiplier": 0.06375,
            "quant_template_output_zero_point": 64,
            "quantize_linear_required_reciprocal_scales": [
                1.0 / record["qparams"]["y_scale"] for record in quant_records
            ],
            "quantize_linear_output_zero_points": [
                record["qparams"]["y_zero_point"] for record in quant_records
            ],
            "quantize_linear_direct_match_count": 0,
            "dequantize_linear_scales": [
                record["qparams"]["x_scale"] for record in dequant_records
            ],
            "dequantize_linear_zero_points": [
                record["qparams"]["x_zero_point"] for record in dequant_records
            ],
            "dequantize_linear_fixed_branch_match_count": sum(
                record["qparams"]["x_scale"] == 1.0
                and _fp32(
                    -record["qparams"]["x_zero_point"]
                    * record["qparams"]["x_scale"]
                )
                == 1.0
                for record in dequant_records
            ),
            "add_dequant_fixed_branch_scale": 1.0,
            "add_dequant_fixed_branch_offset": 1.0,
            "qlinearadd_branch_affine_match_count": add_branch_matches,
            "qlinearadd_branch_count": 2 * len(add_records),
            "qlinearadd_y_qparams_consumed_by_template": False,
        },
    }


def audit_execplan_qparam_binding(source_root: Path) -> dict[str, Any]:
    """Prove that current handlers patch shape/stride fields but no GA qparams."""

    path = source_root / "model_execplan" / "src" / "execution_plan_generator" / "control_registers.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function_names = {
        "quant_from_buffer": "_compute_quant_from_buffer_int32MN_uint8MN_control_register_updates",
        "add_dequant": "_compute_add_dequant_uint8CWH_uint8CWH_fp32CWH_control_register_updates",
    }
    fields: dict[str, list[str]] = {}
    for label, function_name in function_names.items():
        function = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            ),
            None,
        )
        if function is None:
            raise TargetConfigAuditError(f"execplan handler is missing: {function_name}")
        keys: set[str] = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.add(key.value)
        fields[label] = sorted(keys)
    expected_counts = {"quant_from_buffer": 5, "add_dequant": 8}
    if {name: len(value) for name, value in fields.items()} != expected_counts:
        raise TargetConfigAuditError("execplan control-register handler fields differ")
    if any(
        "general_array" in field or "constant" in field
        for values in fields.values()
        for field in values
    ):
        raise TargetConfigAuditError("execplan handler unexpectedly writes a GA qparam constant")
    return {
        "status": "gap_confirmed",
        "path": "model_execplan/src/execution_plan_generator/control_registers.py",
        "sha256": sha256_file(path),
        "handler_fields": fields,
        "current_binding": "shape_and_stream_stride_only",
        "ga_constant_qparams_patched": False,
        "required_change": "extend OperatorSpec with typed scalar qparams and patch validated GA constant fields before encoding",
    }


def inventory_templates(source_root: Path) -> dict[str, Any]:
    json_root = source_root / "jsons"
    paths = sorted(json_root.glob("*.json"))
    records = []
    shared_names = {
        "maxpool_config_16_112_112_stride2_padding1.json",
        "maxpool_config_16_16_16_stride2_padding1.json",
        "avgpool_config_2048_7_7.json",
        "add_dequant_uint8CWH_uint8CWH_fp32CWH.json",
        "quant_from_buffer_int32MN_uint8MN.json",
        "gemv_config_local_M1N128K32.json",
        "sum_config_32_32.json",
    }
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        records.append(
            {
                "path": f"jsons/{path.name}",
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "classification": "resnet_or_shared" if path.name in shared_names else "deepseek_transformer",
                "top_level_groups": sorted(value),
            }
        )
    return {
        "json_count": len(records),
        "resnet_or_shared_count": sum(record["classification"] == "resnet_or_shared" for record in records),
        "deepseek_transformer_count": sum(record["classification"] == "deepseek_transformer" for record in records),
        "named_conv_template_count": sum("conv" in Path(record["path"]).name.lower() for record in records),
        "templates": records,
    }


def audit_register_map(source_root: Path) -> dict[str, Any]:
    """Cross-check the CSV's declared widths against the active encoder layout.

    The official register mapping code deliberately consumes the width prefix and
    row order, not the human-readable [high:low] annotation.  We therefore report
    bad annotations but judge encoder compatibility using declared widths plus
    explicit encoder padding.
    """

    path = source_root / "model_execplan" / "config" / "register_map_with_groups1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    current_group = ""
    current_module = ""
    parsed: list[dict[str, Any]] = []
    annotation_mismatches: list[dict[str, Any]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if not row or all(not item.strip() for item in row):
            continue
        if len(row) < 8:
            row = row + [""] * (8 - len(row))
        if row[0].strip():
            current_group = row[0].strip()
        if row[1].strip():
            current_module = row[1].strip()
        field_text = row[2].strip()
        match = re.search(r"(\d+)\s*bit(?:\[(\d+):(\d+)\])?", field_text)
        if match is None:
            continue
        declared_width = int(match.group(1))
        annotated_width = None
        if match.group(2) is not None:
            annotated_width = abs(int(match.group(2)) - int(match.group(3))) + 1
            if annotated_width != declared_width:
                annotation_mismatches.append(
                    {
                        "line": line_number,
                        "group": current_group,
                        "module": current_module,
                        "config_name": row[3].strip() or None,
                        "declared_width": declared_width,
                        "annotated_width": annotated_width,
                        "annotation": field_text,
                    }
                )
        parsed.append(
            {
                "line": line_number,
                "group": current_group,
                "module": current_module,
                "config_name": row[3].strip() or None,
                "declared_width": declared_width,
                "hardware_port": row[5].strip() or None,
                "meaning": row[4].strip() or row[6].strip() or None,
            }
        )

    maxpool_modules = {
        ("IGA", "20 *DRAM LC"): {"encoder_bits": 60, "encoder_padding_bits": 0},
        ("IGA", "5*BUFFER ROW LC"): {"encoder_bits": 17, "encoder_padding_bits": 0},
        ("IGA", "5*BUFFER COL LC"): {"encoder_bits": 26, "encoder_padding_bits": 0},
        ("IGA", "10*LC PE"): {"encoder_bits": 96, "encoder_padding_bits": 16},
        ("LSU", "4*Read Memory Stream Engine"): {"encoder_bits": 580, "encoder_padding_bits": 0},
        ("LSU", "1*Write Memory Stream Engine"): {"encoder_bits": 496, "encoder_padding_bits": 3},
        ("LSU", "6*Buffer_Manager_Cluster"): {"encoder_bits": 26, "encoder_padding_bits": 0},
        ("GA", "16*PE"): {"encoder_bits": 144, "encoder_padding_bits": 12},
        ("GA", "3*Inport"): {"encoder_bits": 20, "encoder_padding_bits": 0},
        ("GA", "1*Outport"): {"encoder_bits": 12, "encoder_padding_bits": 0},
    }
    module_alignment = []
    for (group, module), expectation in maxpool_modules.items():
        module_rows = [item for item in parsed if item["group"] == group and item["module"] == module]
        declared_total = sum(item["declared_width"] for item in module_rows)
        aligned = declared_total + expectation["encoder_padding_bits"] == expectation["encoder_bits"]
        module_alignment.append(
            {
                "group": group,
                "module": module,
                "declared_field_bits": declared_total,
                **expectation,
                "aligned": aligned,
            }
        )
    if not all(item["aligned"] for item in module_alignment):
        raise TargetConfigAuditError("register-map declared widths do not align with MaxPool encoder modules")

    relevant_prefixes = (
        "dram_loop_configs.",
        "lc_pe_configs.",
        "buffer_loop_configs.",
        "stream_engine.stream.",
        "buffer_config.buffer.",
        "general_array.",
    )
    semantics = [
        item
        for item in parsed
        if item["config_name"] is not None
        and item["config_name"].startswith(relevant_prefixes)
    ]
    probe_script = """
import json
from pathlib import Path
from model_execplan.src.execution_plan_generator.register_mapping import load_register_mapping
p = Path('model_execplan/config')
db = load_register_mapping(p / 'register_map_with_groups1.csv', p / 'config_output.csv')
keys = [
    'iga_lc0.dram_loop_configs.start',
    'rd_stream0.stream_engine.stream.base_addr',
    'buffer_manager_cluster0.buffer_config.buffer.buffer_life_time',
    'ga_pe0.general_array.PE_array.PE.alu_opcode',
    'ga_inport_group0.general_array.inport.mask',
]
print(json.dumps({
    'field_binding_count': len(db.field_bindings),
    'sample_binding_widths': {
        key: db.field_bindings[key].field_high - db.field_bindings[key].field_low + 1
        for key in keys
    },
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe_script],
        cwd=source_root,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONHASHSEED": "0"},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode:
        raise TargetConfigAuditError(f"official register mapping parser failed: {completed.stderr[-2000:]}")
    try:
        consumer_probe = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise TargetConfigAuditError("official register mapping parser returned invalid output") from error
    expected_sample_widths = {
        "iga_lc0.dram_loop_configs.start": 17,
        "rd_stream0.stream_engine.stream.base_addr": 30,
        "buffer_manager_cluster0.buffer_config.buffer.buffer_life_time": 4,
        "ga_pe0.general_array.PE_array.PE.alu_opcode": 5,
        "ga_inport_group0.general_array.inport.mask": 8,
    }
    if (
        consumer_probe.get("field_binding_count") != 739
        or consumer_probe.get("sample_binding_widths") != expected_sample_widths
    ):
        raise TargetConfigAuditError("official register mapping consumer probe differs from expected bindings")

    return {
        "path": "model_execplan/config/register_map_with_groups1.csv",
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "parsed_field_rows": len(parsed),
        "maxpool_semantic_field_rows": len(semantics),
        "maxpool_module_alignment": module_alignment,
        "declared_width_alignment_status": "passed",
        "annotation_range_mismatch_count": len(annotation_mismatches),
        "annotation_range_mismatches": annotation_mismatches,
        "consumer_rule": "model_execplan register_mapping.py uses declared width prefixes and row order; bracketed ranges are intentionally not used for field placement",
        "official_consumer_probe": consumer_probe,
        "semantics": semantics,
    }


def _run_encoder(source_root: Path, config_path: Path, output_dir: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONHASHSEED": "0"})
    command = [
        sys.executable,
        "-m",
        "bitstream.main",
        "-c",
        str(config_path),
        "-o",
        str(output_dir),
        "--seed",
        "42",
        "--heuristic-iterations",
        "10000",
        "--heuristic-restarts",
        "10",
        "--quiet",
    ]
    completed = subprocess.run(
        command,
        cwd=source_root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-4000:]
        raise TargetConfigAuditError(f"official encoder failed with {completed.returncode}: {detail}")
    if "Mapping successful with zero violations" not in completed.stdout:
        raise TargetConfigAuditError("official encoder did not prove zero-violation resource mapping")
    outputs = {}
    for path in sorted(output_dir.iterdir()):
        if path.is_file():
            outputs[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    return {
        "outputs": outputs,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
    }


def _audit_template_encoder(
    source_root: Path,
    template_name: str,
    validator: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    differential_mutation: Callable[[dict[str, Any]], tuple[str, Any, Any]] | None = None,
) -> dict[str, Any]:
    template_path = source_root / "jsons" / template_name
    config = json.loads(template_path.read_text(encoding="utf-8"))
    validation = validator(config)
    with tempfile.TemporaryDirectory(prefix="rtl28-ga-audit-") as temp_text:
        temp = Path(temp_text)
        baseline_a = _run_encoder(source_root, template_path, temp / "baseline-a")
        baseline_b = _run_encoder(source_root, template_path, temp / "baseline-b")
        if baseline_a["outputs"] != baseline_b["outputs"]:
            raise TargetConfigAuditError("official encoder outputs are not deterministic")

        changed = deepcopy(config)
        if differential_mutation is None:
            old_address = _base_address(
                changed["stream_engine"]["stream0"]["base_addr"],
                "stream_engine.stream0.base_addr",
            )
            changed["stream_engine"]["stream0"]["base_addr"] = old_address + 16
            changed_field = "stream_engine.stream0.base_addr"
            original_value: Any = old_address
            modified_value: Any = old_address + 16
        else:
            changed_field, original_value, modified_value = differential_mutation(changed)
        validator(changed)
        changed_path = temp / f"changed-{Path(template_name).stem}.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        changed_run = _run_encoder(source_root, changed_path, temp / "changed")

        binary_name = f"{Path(template_name).stem}_bitstream_128b.bin"
        baseline_hash = baseline_a["outputs"][binary_name]["sha256"]
        changed_binary_name = f"{changed_path.stem}_bitstream_128b.bin"
        changed_hash = changed_run["outputs"][changed_binary_name]["sha256"]
        if baseline_hash == changed_hash:
            raise TargetConfigAuditError("changing stream0.base_addr did not change the encoded bitstream")

    invalid = deepcopy(config)
    invalid["dram_loop_configs"]["LC1"]["end"] = 1 << 17
    try:
        validator(invalid)
    except TargetConfigAuditError as error:
        overflow_rejection = str(error)
    else:
        raise TargetConfigAuditError("overflow mutation was not rejected")

    return {
        "template_path": f"jsons/{template_name}",
        "template_sha256": sha256_file(template_path),
        "preflight_validation": validation,
        "determinism": {
            "status": "passed",
            "run_count": 2,
            "environment": {"PYTHONUTF8": "1", "PYTHONHASHSEED": "0"},
            "seed": 42,
            "heuristic_iterations": 10000,
            "heuristic_restarts": 10,
            "outputs": baseline_a["outputs"],
        },
        "differential_sensitivity": {
            "status": "passed",
            "field": changed_field,
            "original": original_value,
            "modified": modified_value,
            "baseline_128b_sha256": baseline_hash,
            "modified_128b_sha256": changed_hash,
        },
        "fail_closed": {
            "status": "passed",
            "mutation": "dram_loop_configs.LC1.end=131072",
            "rejection": overflow_rejection,
        },
    }


def _mutate_quant_multiplier(config: dict[str, Any]) -> tuple[str, Any, Any]:
    path = "general_array.PE_array.PE00.inport1.constant"
    port = config["general_array"]["PE_array"]["PE00"]["inport1"]
    original = port["constant"]
    port["constant"] = 0.125
    return path, original, port["constant"]


def _mutate_add_dequant_scale(config: dict[str, Any]) -> tuple[str, Any, Any]:
    path = "general_array.PE_array.PE00.inport1.constant"
    port = config["general_array"]["PE_array"]["PE00"]["inport1"]
    original = port["constant"]
    port["constant"] = 2.0
    return path, original, port["constant"]


def audit_maxpool_encoder(source_root: Path) -> dict[str, Any]:
    """Keep the original first-MaxPool probe as a stable compatibility entry."""

    return _audit_template_encoder(
        source_root,
        MAXPOOL_TEMPLATE,
        validate_maxpool_template,
    )


def audit_pool_family(
    source_root: Path,
    *,
    first_maxpool_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit both MaxPool templates and the partial AvgPool reduction template."""

    json_root = source_root / "jsons"
    first = json.loads((json_root / MAXPOOL_TEMPLATE).read_text(encoding="utf-8"))
    second = json.loads((json_root / SECOND_MAXPOOL_TEMPLATE).read_text(encoding="utf-8"))
    avgpool = json.loads((json_root / AVGPOOL_TEMPLATE).read_text(encoding="utf-8"))
    linkage = extract_pool_family_linkage(first, second, avgpool)
    probes = {
        MAXPOOL_TEMPLATE: first_maxpool_probe
        if first_maxpool_probe is not None
        else audit_maxpool_encoder(source_root),
        SECOND_MAXPOOL_TEMPLATE: _audit_template_encoder(
            source_root,
            SECOND_MAXPOOL_TEMPLATE,
            validate_maxpool_template,
        ),
        AVGPOOL_TEMPLATE: _audit_template_encoder(
            source_root,
            AVGPOOL_TEMPLATE,
            validate_avgpool_template,
        ),
    }
    for template_name, probe in probes.items():
        if (
            probe.get("determinism", {}).get("status") != "passed"
            or probe.get("differential_sensitivity", {}).get("status") != "passed"
            or probe.get("fail_closed", {}).get("status") != "passed"
        ):
            raise TargetConfigAuditError(f"Pool encoder probe did not pass: {template_name}")
    return {
        "status": "passed",
        "template_count": len(probes),
        "linkage": linkage,
        "encoder_probes": probes,
        "numerical_scope": {
            "status": "not_validated",
            "maxpool_unsigned_semantics": "unresolved",
            "avgpool_requantization": "absent_from_template",
            "target_simulator_outputs": "unavailable",
            "hardware_outputs": "unavailable",
        },
    }


def audit_ga_quant_add(
    source_root: Path,
    *,
    model_path: Path,
    model_sha256: str,
) -> dict[str, Any]:
    """Audit the common GA crosswalk while keeping numerical gates fail-closed."""

    json_root = source_root / "jsons"
    quant = json.loads((json_root / QUANT_TEMPLATE).read_text(encoding="utf-8"))
    add_dequant = json.loads(
        (json_root / ADD_DEQUANT_TEMPLATE).read_text(encoding="utf-8")
    )
    crosswalk = extract_ga_quant_add_crosswalk(quant, add_dequant)
    probes = {
        QUANT_TEMPLATE: _audit_template_encoder(
            source_root,
            QUANT_TEMPLATE,
            validate_quant_template,
            differential_mutation=_mutate_quant_multiplier,
        ),
        ADD_DEQUANT_TEMPLATE: _audit_template_encoder(
            source_root,
            ADD_DEQUANT_TEMPLATE,
            validate_add_dequant_template,
            differential_mutation=_mutate_add_dequant_scale,
        ),
    }
    for template_name, probe in probes.items():
        if (
            probe.get("determinism", {}).get("status") != "passed"
            or probe.get("differential_sensitivity", {}).get("status") != "passed"
            or probe.get("fail_closed", {}).get("status") != "passed"
        ):
            raise TargetConfigAuditError(f"GA encoder probe did not pass: {template_name}")
    return {
        "status": "passed_with_numerical_gaps",
        "template_count": 2,
        "crosswalk": crosswalk,
        "resnet_scalar_qparams": audit_resnet_scalar_qparams(
            model_path,
            expected_sha256=model_sha256,
        ),
        "execplan_qparam_binding": audit_execplan_qparam_binding(source_root),
        "encoder_probes": probes,
        "numerical_scope": {
            "status": "not_validated",
            "quant_rounding_recipe": "identified_not_target_executed",
            "quant_uint8_saturation": "rtl_static_semantics_identified",
            "add_dequant_fp32_affine_sum": "constants_patchable_not_target_executed",
            "complete_qlinearadd": "absent",
            "target_simulator_outputs": "unavailable",
            "hardware_outputs": "unavailable",
        },
    }


def build_authority_report(source_root: Path) -> dict[str, Any]:
    resolved = source_root.resolve()
    git = subprocess.run(
        ["git", "-c", f"safe.directory={resolved}", "rev-parse", "HEAD"],
        cwd=resolved,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if git.returncode or git.stdout.strip() != OFFICIAL_CONFIG_COMMIT:
        raise TargetConfigAuditError("official configuration checkout does not match the locked commit")
    status = subprocess.run(
        ["git", "-c", f"safe.directory={resolved}", "status", "--short"],
        cwd=resolved,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if status.returncode or status.stdout.strip():
        raise TargetConfigAuditError("official configuration checkout must be clean")
    implementation_paths = [
        "bitstream/main.py",
        "bitstream/parse.py",
        "bitstream/bit.py",
        "bitstream/config/loop.py",
        "bitstream/config/stream.py",
        "bitstream/config/buffer.py",
        "bitstream/config/general.py",
        "model_execplan/README.md",
        "model_execplan/config/register_map_with_groups1.csv",
        "model_execplan/config/config_output.csv",
        "model_execplan/src/execution_plan_generator/register_mapping.py",
        "model_execplan/src/execution_plan_generator/control_registers.py",
    ]
    maxpool_probe = audit_maxpool_encoder(source_root)
    pool_family_probe = audit_pool_family(
        source_root,
        first_maxpool_probe=maxpool_probe,
    )
    project_root = source_root.parent
    model_graph_path = project_root / "artifacts" / "w3" / "model_graph.json"
    model_graph = json.loads(model_graph_path.read_text(encoding="utf-8"))
    ga_quant_add_probe = audit_ga_quant_add(
        source_root,
        model_path=project_root
        / "artifacts"
        / "reference_model"
        / "resnet50-v1-12-int8.onnx",
        model_sha256=model_graph["model_sha256"],
    )
    return {
        "schema_version": "0.3",
        "report_kind": "official_target_config_authority_audit",
        "status": "configuration_source_verified",
        "source": {
            "repository": OFFICIAL_CONFIG_REPOSITORY,
            "commit": OFFICIAL_CONFIG_COMMIT,
            "slice_count": OFFICIAL_CONFIG_SLICE_COUNT,
            "authoritative_paths": ["jsons", "bitstream", "model_execplan"],
            "implementation_files": [
                {
                    "path": path,
                    "sha256": sha256_file(source_root / path),
                    "size_bytes": (source_root / path).stat().st_size,
                }
                for path in implementation_paths
            ],
        },
        "authority_scope": {
            "approved_for": [
                "target_json_configuration_format",
                "target_bitstream_encoding_and_mapping",
                "target_execplan_configuration_chain",
            ],
            "not_proven_by_this_audit": [
                "target_simulator_numerical_correctness",
                "resnet50_operator_coverage",
                "clean_rtl_elaboration",
                "board_load_start_wait_dump_protocol",
                "golden_simulator_hardware_equality",
                "uint8_maxpool_comparison_semantics",
                "qlinear_global_average_pool_requantization",
                "quant_rounding_target_execution",
                "complete_qlinearadd_from_add_dequant_template",
            ],
        },
        "inventory": inventory_templates(source_root),
        "register_map_audit": audit_register_map(source_root),
        "maxpool_probe": maxpool_probe,
        "pool_family_probe": pool_family_probe,
        "ga_quant_add_probe": ga_quant_add_probe,
        "encoder_safety_findings": [
            "The official Bit type masks values modulo field width; the project preflight must reject overflow before encoding.",
            "A fixed mapper seed alone is insufficient across fresh Python processes; PYTHONHASHSEED=0 is required.",
            "PYTHONUTF8=1 is required on Windows so diagnostic symbols do not fail under a GBK console.",
        ],
    }
