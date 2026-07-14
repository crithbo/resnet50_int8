from __future__ import annotations

import csv
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


OFFICIAL_CONFIG_REPOSITORY = "https://github.com/uSFrances/ndp-sim.git"
OFFICIAL_CONFIG_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
OFFICIAL_CONFIG_SLICE_COUNT = 28
MAXPOOL_TEMPLATE = "maxpool_config_16_112_112_stride2_padding1.json"

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
    if isinstance(constant, int) and not isinstance(constant, bool):
        if not -(1 << (constant_width - 1)) <= constant < 1 << constant_width:
            raise TargetConfigAuditError(
                f"{path}.constant={constant} exceeds the {constant_width}-bit encoded field"
            )


def _validate_maxpool_stream(value: Any, path: str) -> str:
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
    _uint(stream.get("base_addr"), 30, f"{path}.base_addr")
    if stream["base_addr"] % 16:
        raise TargetConfigAuditError(f"{path}.base_addr must be 16-byte aligned")
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


def validate_maxpool_template(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the official MaxPool template before invoking its wrapping encoder."""

    expected_top = {
        "CONFIG",
        "dram_loop_configs",
        "lc_pe_configs",
        "buffer_loop_configs",
        "stream_engine",
        "buffer_config",
        "general_array",
    }
    _exact_keys(config, expected_top, "maxpool config")
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
    modes = [_validate_maxpool_stream(value, f"stream_engine.{key}") for key, value in streams.items()]
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
        if pe.get("alu_opcode") != "int8_max":
            raise TargetConfigAuditError(f"general_array.PE_array.{name} must use int8_max")
        _uint(pe.get("transout_last_index"), 4, f"general_array.PE_array.{name}.transout_last_index")
        for index in range(3):
            _validate_loop_port(
                pe.get(f"inport{index}"),
                f"general_array.PE_array.{name}.inport{index}",
                src_width=3,
                constant_width=32,
            )

    return {
        "status": "valid",
        "config_mask": mask,
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


def audit_maxpool_encoder(source_root: Path) -> dict[str, Any]:
    template_path = source_root / "jsons" / MAXPOOL_TEMPLATE
    config = json.loads(template_path.read_text(encoding="utf-8"))
    validation = validate_maxpool_template(config)
    with tempfile.TemporaryDirectory(prefix="rtl28-maxpool-audit-") as temp_text:
        temp = Path(temp_text)
        baseline_a = _run_encoder(source_root, template_path, temp / "baseline-a")
        baseline_b = _run_encoder(source_root, template_path, temp / "baseline-b")
        if baseline_a["outputs"] != baseline_b["outputs"]:
            raise TargetConfigAuditError("official encoder outputs are not deterministic")

        changed = deepcopy(config)
        old_address = changed["stream_engine"]["stream0"]["base_addr"]
        changed["stream_engine"]["stream0"]["base_addr"] = old_address + 16
        validate_maxpool_template(changed)
        changed_path = temp / "changed-base-address.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        changed_run = _run_encoder(source_root, changed_path, temp / "changed")

        binary_name = f"{Path(MAXPOOL_TEMPLATE).stem}_bitstream_128b.bin"
        baseline_hash = baseline_a["outputs"][binary_name]["sha256"]
        changed_hash = changed_run["outputs"]["changed-base-address_bitstream_128b.bin"]["sha256"]
        if baseline_hash == changed_hash:
            raise TargetConfigAuditError("changing stream0.base_addr did not change the encoded bitstream")

    invalid = deepcopy(config)
    invalid["dram_loop_configs"]["LC1"]["end"] = 1 << 17
    try:
        validate_maxpool_template(invalid)
    except TargetConfigAuditError as error:
        overflow_rejection = str(error)
    else:
        raise TargetConfigAuditError("overflow mutation was not rejected")

    return {
        "template_path": f"jsons/{MAXPOOL_TEMPLATE}",
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
            "field": "stream_engine.stream0.base_addr",
            "original": old_address,
            "modified": old_address + 16,
            "baseline_128b_sha256": baseline_hash,
            "modified_128b_sha256": changed_hash,
        },
        "fail_closed": {
            "status": "passed",
            "mutation": "dram_loop_configs.LC1.end=131072",
            "rejection": overflow_rejection,
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
    return {
        "schema_version": "0.1",
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
            ],
        },
        "inventory": inventory_templates(source_root),
        "register_map_audit": audit_register_map(source_root),
        "maxpool_probe": audit_maxpool_encoder(source_root),
        "encoder_safety_findings": [
            "The official Bit type masks values modulo field width; the project preflight must reject overflow before encoding.",
            "A fixed mapper seed alone is insufficient across fresh Python processes; PYTHONHASHSEED=0 is required.",
            "PYTHONUTF8=1 is required on Windows so diagnostic symbols do not fail under a GBK console.",
        ],
    }
