from __future__ import annotations

import hashlib
import json
import math
import re
from fractions import Fraction
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SUBSYSTEMS = ("IGA", "LSU", "SA", "GA")
SUBSYSTEM_KEYS: dict[str, tuple[str, ...]] = {
    "IGA": ("dram_loop_configs", "lc_pe_configs", "buffer_loop_configs"),
    "LSU": ("stream_engine", "buffer_config", "n2n"),
    "SA": ("special_array",),
    "GA": ("general_array",),
}
ROOT_KEYS = {
    "CONFIG",
    "dram_loop_configs",
    "lc_pe_configs",
    "buffer_loop_configs",
    "stream_engine",
    "buffer_config",
    "n2n",
    "special_array",
    "general_array",
    "gemm_shape",
    "gemv_shape",
}
TARGETS = {"A", "B", "B'", "C", "D"}
INDEX_MODES = {None, "buffer", "keep", "constant"}
PORT_MODES = {None, "buffer", "keep", "constant"}
SA_LABEL_TO_ENCODED_MAJOR = {"col": 0, "row": 1}
GA_OPCODES = {
    "add",
    "sub",
    "mul",
    "max",
    "sum",
    "summac",
    "mac",
    "int8_max",
    "int32_sum",
    "int32_sub",
    "int32_mac",
    "rec",
    "sqrt",
    "rec_sqrt",
    "sfu_activation",
}
GA_SFU_OPCODES = {"rec", "sqrt", "rec_sqrt", "sfu_activation"}
GA_OPERAND_PORTS = {
    "add": {0, 1},
    "sub": {0, 1},
    "mul": {0, 1},
    "max": {0, 2},
    "sum": {0, 2},
    "summac": {0, 1, 2},
    "mac": {0, 1, 2},
    # INT8 transout hard-wires C=0 on its first item and feeds C from the
    # outbuffer afterwards; the JSON-side operand is therefore A only.
    "int8_max": {0},
    "int32_sum": {0, 2},
    "int32_sub": {0, 1},
    "int32_mac": {0, 1, 2},
    "rec": {0},
    "sqrt": {0},
    "rec_sqrt": {0},
    "sfu_activation": {0},
}


@dataclass(frozen=True)
class TargetProfile:
    slices: int = 28
    banks_per_slice: int = 4
    ddr_rows: int = 6144
    ddr_columns: int = 64
    subwords_per_column: int = 16
    read_streams: int = 4
    write_streams: int = 1
    buffers: int = 6


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


@dataclass
class ConfigState:
    """Persistent configure-register identity after a stage has been parsed."""

    fingerprints: dict[str, str | None] = field(
        default_factory=lambda: {name: None for name in SUBSYSTEMS}
    )

    def copy(self) -> "ConfigState":
        return ConfigState(dict(self.fingerprints))


@dataclass
class ValidationReport:
    source: str
    valid: bool
    issues: list[ValidationIssue]
    facts: dict[str, Any]
    next_state: ConfigState

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "operator-config-validation-report-v1",
            "source": self.source,
            "valid": self.valid,
            "first_error": asdict(self.issues[0]) if self.issues else None,
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
            "next_config_state": dict(self.next_state.fingerprints),
        }


def encoded_sa_major(label: str) -> int:
    if label not in SA_LABEL_TO_ENCODED_MAJOR:
        raise ValueError(f"unsupported SA outport label: {label!r}")
    return SA_LABEL_TO_ENCODED_MAJOR[label]


def route_sa_outport(
    values: Sequence[Sequence[Any]], encoded_major_bit: int
) -> tuple[tuple[Any, ...], ...]:
    """Model the exact two assignments in SA_Outport_Connect.sv.

    Bit 0 preserves [out][source]. Bit 1 drives [out][source] from
    [source][out], i.e. transposes the square SA result matrix.
    """

    rows = tuple(tuple(row) for row in values)
    if not rows or any(len(row) != len(rows) for row in rows):
        raise ValueError("SA outport micro-model requires a non-empty square matrix")
    if encoded_major_bit == 0:
        return rows
    if encoded_major_bit == 1:
        return tuple(tuple(rows[source][out] for source in range(len(rows))) for out in range(len(rows)))
    raise ValueError("encoded_major_bit must be 0 or 1")


def keep_releases(last: bool, last_index: int, configured_last_index: int) -> bool:
    """RTL keep ports release on last && last_index <= configured threshold."""

    return bool(last and last_index <= configured_last_index)


def read_lane_value(
    value: int,
    indexes: Sequence[int],
    *,
    padding_enable: Sequence[int],
    padding_low: Sequence[int | None],
    padding_up: Sequence[int | None],
    padding_value: int,
    tailing_enable: Sequence[int],
    tailing_low: Sequence[int | None],
    tailing_up: Sequence[int | None],
) -> int:
    """Micro-model RD_Data_Channel priority: padding, then tailing zero."""

    padded = _outside_enabled_bounds(indexes, padding_enable, padding_low, padding_up)
    tailed = _outside_enabled_bounds(indexes, tailing_enable, tailing_low, tailing_up)
    if padded:
        return padding_value
    if tailed:
        return 0
    return value


def write_lane_value(
    new_value: int,
    old_value: int,
    indexes: Sequence[int],
    *,
    tailing_enable: Sequence[int],
    tailing_low: Sequence[int | None],
    tailing_up: Sequence[int | None],
) -> int:
    """Micro-model WR_Data_Channel tailing merge with existing DDR data."""

    if _outside_enabled_bounds(indexes, tailing_enable, tailing_low, tailing_up):
        return old_value
    return new_value


def _outside_enabled_bounds(
    indexes: Sequence[int],
    enable: Sequence[int],
    low: Sequence[int | None],
    up: Sequence[int | None],
) -> bool:
    if not (len(indexes) == len(enable) == len(low) == len(up)):
        raise ValueError("bound vectors must have equal arity")
    return any(
        bool(enabled) and (lo is None or hi is None or index < lo or index > hi)
        for index, enabled, lo, hi in zip(indexes, enable, low, up, strict=True)
    )


class OperatorConfigValidator:
    """Peripheral, fail-closed checker for the active ndp-sim JSON format.

    This module deliberately does not import or mutate ndp-sim. It validates
    source values before the native encoder can silently ignore, default, or
    truncate them.
    """

    def __init__(self, profile: TargetProfile | None = None) -> None:
        self.profile = profile or TargetProfile()
        self._issues: list[ValidationIssue] = []
        self._facts: dict[str, Any] = {}

    def validate(
        self,
        config: Mapping[str, Any],
        *,
        source: str = "<memory>",
        previous_state: ConfigState | None = None,
        development_mode: bool = False,
        expected_sa_transpose: bool | None = None,
    ) -> ValidationReport:
        self._issues = []
        self._facts = {"target_profile": asdict(self.profile)}
        state = (previous_state or ConfigState()).copy()

        if not isinstance(config, Mapping):
            self._error("SCHEMA.TYPE", "$", "root must be a JSON object")
            return self._report(source, state)

        self._exact_known_keys(config, ROOT_KEYS, "$")
        mask = self._validate_config_mask(config.get("CONFIG"))
        if mask is not None:
            state = self._transition_config_state(config, mask, state)

        self._validate_shape_metadata(config)
        self._validate_dram_loops(config.get("dram_loop_configs", {}))
        self._validate_lc_pes(config.get("lc_pe_configs", {}))
        self._validate_buffer_loops(config.get("buffer_loop_configs", {}))
        streams = self._validate_streams(config.get("stream_engine", {}))
        buffers = self._validate_buffers(config.get("buffer_config", {}))
        self._validate_buffer_topology(config, streams, buffers)
        self._validate_n2n(config.get("n2n", {}), buffers)
        self._validate_sa(
            config.get("special_array"),
            development_mode=development_mode,
            expected_sa_transpose=expected_sa_transpose,
        )
        self._validate_ga(config.get("general_array"))
        self._validate_terminal_chain(config, streams)
        self._validate_sa_pingpong(config, streams)

        self._facts["issue_count"] = len(self._issues)
        return self._report(source, state)

    def validate_file(
        self,
        path: Path,
        **kwargs: Any,
    ) -> ValidationReport:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._issues = [ValidationIssue("JSON.PARSE", "$", str(error))]
            self._facts = {"target_profile": asdict(self.profile), "issue_count": 1}
            return self._report(str(path), kwargs.get("previous_state") or ConfigState())
        return self.validate(value, source=str(path), **kwargs)

    def _report(self, source: str, state: ConfigState) -> ValidationReport:
        return ValidationReport(
            source=source,
            valid=not self._issues,
            issues=list(self._issues),
            facts=dict(self._facts),
            next_state=state,
        )

    def _error(self, code: str, path: str, message: str) -> None:
        self._issues.append(ValidationIssue(code, path, message))

    def _exact_known_keys(
        self, value: Mapping[str, Any], allowed: set[str], path: str
    ) -> None:
        for key in sorted(set(value) - allowed):
            self._error("SCHEMA.UNKNOWN_FIELD", f"{path}.{key}", "field is not consumed by the active format")

    def _exact_keys(self, value: Any, expected: set[str], path: str) -> Mapping[str, Any] | None:
        if not isinstance(value, Mapping):
            self._error("SCHEMA.TYPE", path, "must be an object")
            return None
        for key in sorted(expected - set(value)):
            self._error("SCHEMA.MISSING_FIELD", f"{path}.{key}", "required field is missing")
        for key in sorted(set(value) - expected):
            self._error("SCHEMA.UNKNOWN_FIELD", f"{path}.{key}", "field is not encoded here")
        return value

    def _uint(self, value: Any, width: int, path: str, *, nullable: bool = False) -> bool:
        if nullable and value is None:
            return True
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << width):
            self._error("VALUE.UINT_RANGE", path, f"must fit unsigned {width}-bit range")
            return False
        return True

    def _bits(self, value: Any, length: int, path: str) -> bool:
        if not isinstance(value, list) or len(value) != length or any(item not in (0, 1) for item in value):
            self._error("VALUE.BIT_VECTOR", path, f"must contain exactly {length} binary integers")
            return False
        return True

    def _list(self, value: Any, length: int, path: str) -> list[Any] | None:
        if not isinstance(value, list) or len(value) != length:
            self._error("VALUE.ARITY", path, f"must contain exactly {length} values")
            return None
        return value

    def _validate_config_mask(self, value: Any) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
        if not isinstance(value, str) or len(value) != 8 or set(value) - {"0", "1"}:
            self._error("CONFIG.MASK", "$.CONFIG", "must be an eight-bit binary string")
            return None
        bits = tuple(int(bit) for bit in value)
        enables, updates = bits[:4], bits[4:]
        self._facts["config"] = {
            name: {"enable": enables[index], "update": updates[index]}
            for index, name in enumerate(SUBSYSTEMS)
        }
        return enables, updates

    def _transition_config_state(
        self,
        config: Mapping[str, Any],
        mask: tuple[tuple[int, ...], tuple[int, ...]],
        state: ConfigState,
    ) -> ConfigState:
        enables, updates = mask
        next_state = state.copy()
        for index, name in enumerate(SUBSYSTEMS):
            enable, update = enables[index], updates[index]
            present = any(key in config for key in SUBSYSTEM_KEYS[name])
            if not enable:
                if update:
                    self._error(
                        "CONFIG.DISABLED_UPDATE",
                        "$.CONFIG",
                        f"{name} has enable=0/update=1; RTL clears it and parsed payload has no stage meaning",
                    )
                if present:
                    self._error(
                        "CONFIG.DISABLED_BODY",
                        "$.CONFIG",
                        f"{name} is disabled but its ignored configuration body is still present",
                    )
                next_state.fingerprints[name] = None
                continue
            fingerprint = self._subsystem_fingerprint(config, name)
            if update:
                if name in ("SA", "GA") and not present:
                    self._error(
                        "CONFIG.UPDATE_WITHOUT_BODY",
                        "$.CONFIG",
                        f"{name} is enabled and updated but its configuration body is absent",
                    )
                next_state.fingerprints[name] = fingerprint
                continue
            prior = state.fingerprints.get(name)
            if prior is None:
                self._error(
                    "CONFIG.REUSE_WITHOUT_STATE",
                    "$.CONFIG",
                    f"{name} enable=1/update=0 requires initialized state from an earlier stage",
                )
            elif present and fingerprint != prior:
                self._error(
                    "CONFIG.REUSE_DRIFT",
                    "$.CONFIG",
                    f"{name} body differs from retained hardware state while update=0",
                )
            next_state.fingerprints[name] = prior
        return next_state

    @staticmethod
    def _subsystem_fingerprint(config: Mapping[str, Any], subsystem: str) -> str:
        body = {key: config.get(key) for key in SUBSYSTEM_KEYS[subsystem]}
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _validate_shape_metadata(self, config: Mapping[str, Any]) -> None:
        for name in ("gemm_shape", "gemv_shape"):
            if name not in config:
                continue
            shape = self._exact_keys(config[name], {"M", "N", "K"}, f"$.{name}")
            if shape is not None:
                for axis in ("M", "N", "K"):
                    value = shape.get(axis)
                    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                        self._error("VALUE.POSITIVE", f"$.{name}.{axis}", "must be a positive integer")

    def _validate_dram_loops(self, raw: Any) -> None:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.dram_loop_configs", "must be an object")
            return
        if len(raw) > 20:
            self._error("RESOURCE.LIMIT", "$.dram_loop_configs", "hardware has 20 DRAM loop controllers")
        for name, value in raw.items():
            path = f"$.dram_loop_configs.{name}"
            if not re.fullmatch(r"LC(?:[0-9]|1[0-9])", name):
                self._error("RESOURCE.NAME", path, "must be LC0..LC19")
            loop = self._exact_keys(value, {"src_id", "outmost_loop", "start", "end", "stride", "last_index"}, path)
            if loop is None:
                continue
            self._uint(loop.get("outmost_loop"), 1, f"{path}.outmost_loop")
            for field_name in ("start", "end"):
                value_i = loop.get(field_name)
                if isinstance(value_i, bool) or not isinstance(value_i, int) or not -(1 << 16) <= value_i < (1 << 16):
                    self._error("VALUE.SIGNED_RANGE", f"{path}.{field_name}", "must fit signed 17-bit range")
            self._uint(loop.get("stride"), 17, f"{path}.stride")
            self._uint(loop.get("last_index"), 4, f"{path}.last_index")
            active = bool(loop.get("outmost_loop")) or loop.get("src_id") is not None
            if active and (
                not isinstance(loop.get("stride"), int)
                or loop.get("stride", 0) <= 0
                or not isinstance(loop.get("start"), int)
                or not isinstance(loop.get("end"), int)
                or loop.get("start") >= loop.get("end")
            ):
                self._error("LOOP.NON_PROGRESS", path, "active loop requires start < end and stride > 0")

    def _validate_lc_pes(self, raw: Any) -> None:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.lc_pe_configs", "must be an object")
            return
        if len(raw) > 10:
            self._error("RESOURCE.LIMIT", "$.lc_pe_configs", "hardware has 10 LC PEs")
        for name, value in raw.items():
            path = f"$.lc_pe_configs.{name}"
            if not re.fullmatch(r"PE[0-9]", name):
                self._error("RESOURCE.NAME", path, "must be PE0..PE9")
            pe = self._exact_keys(value, {"alu_opcode", "inport0", "inport1", "inport2"}, path)
            if pe is None:
                continue
            if pe.get("alu_opcode") not in {"add", "mul", "mac"}:
                self._error("VALUE.ENUM", f"{path}.alu_opcode", "unsupported LC PE opcode")
            opcode = pe.get("alu_opcode")
            modes: list[Any] = []
            for index in range(3):
                mode = self._validate_compute_port(
                    pe.get(f"inport{index}"),
                    f"{path}.inport{index}",
                    16,
                    integer_constant_only=True,
                )
                modes.append(mode)
            if modes.count("buffer") != 1:
                self._error("TAG.CARRIER_COUNT", path, "LC PE requires exactly one buffer-mode terminal-tag carrier")
            used_ports = {0, 1, 2} if opcode == "mac" else {0, 1}
            for index, mode in enumerate(modes):
                if index in used_ports and mode is None:
                    self._error(
                        "LC_PE.OPERAND_DISABLED",
                        f"{path}.inport{index}.mode",
                        f"{opcode} consumes inport{index}; null mode leaves the RTL operand uninitialized",
                    )
                if index not in used_ports and mode is not None:
                    self._error(
                        "LC_PE.UNUSED_OPERAND_ENABLED",
                        f"{path}.inport{index}.mode",
                        f"{opcode} ignores inport{index} numerically but an enabled port still gates RTL matching/backpressure",
                    )

    def _validate_compute_port(
        self,
        raw: Any,
        path: str,
        constant_width: int,
        *,
        integer_constant_only: bool = False,
    ) -> Any:
        port = self._exact_keys(raw, {"src_id", "mode", "keep_last_index", "constant"}, path)
        if port is None:
            return None
        mode = port.get("mode")
        if mode not in PORT_MODES:
            self._error("VALUE.ENUM", f"{path}.mode", "unsupported port mode")
            return mode
        self._uint(port.get("keep_last_index"), 4, f"{path}.keep_last_index", nullable=True)
        source = port.get("src_id")
        if mode in ("buffer", "keep") and source is None:
            self._error("GRAPH.MISSING_SOURCE", f"{path}.src_id", f"{mode} mode requires a source")
        if mode is None and source is not None:
            self._error("GRAPH.UNUSED_SOURCE", f"{path}.src_id", "null mode must not carry a source")
        if mode == "constant" and source is not None:
            self._error("GRAPH.UNUSED_SOURCE", f"{path}.src_id", "constant mode ignores the source selector")
        if mode == "keep" and port.get("keep_last_index") is None:
            self._error("TAG.KEEP_THRESHOLD", f"{path}.keep_last_index", "keep mode requires a last-index threshold")
        if mode != "keep" and port.get("keep_last_index") is not None:
            self._error(
                "TAG.UNUSED_KEEP_THRESHOLD",
                f"{path}.keep_last_index",
                "keep_last_index is consumed only when mode is keep",
            )
        self._validate_constant(
            port.get("constant"),
            mode,
            constant_width,
            f"{path}.constant",
            integer_only=integer_constant_only,
        )
        return mode

    def _validate_constant(
        self,
        value: Any,
        mode: Any,
        width: int,
        path: str,
        *,
        integer_only: bool = False,
    ) -> None:
        if value is None:
            if mode == "constant":
                self._error("VALUE.NUMERIC", path, "constant mode requires an explicit value")
            return
        if integer_only and mode == "constant":
            if isinstance(value, bool):
                self._error("LC_PE.CONSTANT_DOMAIN", path, "LC PE constants must be signed integers or exact hexadecimal bit patterns")
                return
            if isinstance(value, int):
                if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
                    self._error("VALUE.SIGNED_RANGE", path, f"LC PE integer constant must fit signed {width}-bit range")
                return
            if isinstance(value, str):
                compact = value.strip().replace("_", "")
                if re.fullmatch(r"0[xX][0-9a-fA-F]+", compact):
                    if int(compact, 16) >= (1 << width):
                        self._error("VALUE.UINT_RANGE", path, f"raw hexadecimal pattern must fit {width} bits")
                    return
            self._error(
                "LC_PE.CONSTANT_DOMAIN",
                path,
                "LC PE RTL is a 16-bit integer ALU; floating/fractional constants would be truncated FP32 bit patterns",
            )
            return
        parsed: int | float
        if isinstance(value, bool):
            self._error("VALUE.NUMERIC", path, "boolean is not a numeric constant")
            return
        if isinstance(value, str):
            compact = value.strip().replace(" ", "")
            try:
                if compact.lower().startswith("0x") and "/" not in compact:
                    parsed = int(compact, 16)
                    if not 0 <= parsed < (1 << width):
                        self._error("VALUE.UINT_RANGE", path, f"raw hexadecimal pattern must fit {width} bits")
                    return
                if "/" in compact:
                    numerator, denominator = compact.split("/", 1)
                    parsed = float(Fraction(numerator)) / float(Fraction(denominator))
                else:
                    parsed = float(Fraction(compact))
            except (ValueError, ZeroDivisionError):
                self._error("VALUE.NUMERIC", path, "constant string must be exact hex, number, or one finite fraction")
                return
        elif isinstance(value, (int, float)):
            parsed = value
        else:
            self._error("VALUE.NUMERIC", path, "must be a finite numeric value")
            return
        if isinstance(parsed, float):
            if not math.isfinite(parsed):
                self._error("VALUE.NUMERIC", path, "floating constant must be finite")
        elif not -(1 << (width - 1)) <= parsed < (1 << width):
            self._error("VALUE.SIGNED_RANGE", path, f"integer constant does not fit the {width}-bit encoded field")

    def _validate_buffer_loops(self, raw: Any) -> None:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.buffer_loop_configs", "must be an object")
            return
        if len(raw) > 5:
            self._error("RESOURCE.LIMIT", "$.buffer_loop_configs", "hardware has five ROW/COL loop groups")
        targets: list[Any] = []
        for name, value in raw.items():
            path = f"$.buffer_loop_configs.{name}"
            if not re.fullmatch(r"GROUP[0-4]", name):
                self._error("RESOURCE.NAME", path, "must be GROUP0..GROUP4")
            group = self._exact_keys(value, {"target", "ROW_LC", "COL_LC"}, path)
            if group is None:
                continue
            target = group.get("target")
            targets.append(target)
            if target not in TARGETS:
                self._error("VALUE.ENUM", f"{path}.target", "unsupported logical target")
            for kind, width in (("ROW_LC", 3), ("COL_LC", 6)):
                lp = f"{path}.{kind}"
                loop = self._exact_keys(group.get(kind), {"src_id", "start", "end", "stride", "last_index"}, lp)
                if loop is None:
                    continue
                for field_name in ("start", "end", "stride"):
                    self._uint(loop.get(field_name), width, f"{lp}.{field_name}")
                self._uint(loop.get("last_index"), 4, f"{lp}.last_index")
                if (
                    not isinstance(loop.get("stride"), int)
                    or loop.get("stride", 0) <= 0
                    or not isinstance(loop.get("start"), int)
                    or not isinstance(loop.get("end"), int)
                    or loop.get("start") >= loop.get("end")
                ):
                    self._error("LOOP.NON_PROGRESS", lp, "ROW/COL loop requires start < end and stride > 0")
        duplicates = sorted({target for target in targets if targets.count(target) > 1 and target is not None})
        if duplicates:
            self._error("TOPOLOGY.DUPLICATE_TARGET", "$.buffer_loop_configs", f"duplicate logical targets: {duplicates}")

    def _validate_streams(self, raw: Any) -> dict[str, Mapping[str, Any]]:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.stream_engine", "must be an object")
            return {}
        streams: dict[str, Mapping[str, Any]] = {}
        read_count = 0
        write_count = 0
        seen_targets: list[str] = []
        for name, value in raw.items():
            path = f"$.stream_engine.{name}"
            if not re.fullmatch(r"stream[0-4]", name):
                self._error("RESOURCE.NAME", path, "must be stream0..stream4")
            if not isinstance(value, Mapping):
                self._error("SCHEMA.TYPE", path, "must be an object")
                continue
            mode = value.get("mode")
            if mode not in ("read", "write"):
                self._error("VALUE.ENUM", f"{path}.mode", "must be read or write")
                continue
            common = {
                "target", "mode", "base_addr", "mem_idx_mode", "mem_idx_keep_last_index",
                "mem_idx_constant", "idx", "idx_size", "dim_stride", "tailing_enable",
                "idx_tailing_range", "address_remapping", "buf_idx_mode",
                "buf_idx_keep_last_index", "buf_spatial_stride", "buf_spatial_size",
                "ping_pong", "pingpong_last_index",
            }
            read_only = {"padding_enable", "padding_reg_value", "idx_padding_range", "buf_full_last_index"}
            expected = common | (read_only if mode == "read" else set())
            self._exact_keys(value, expected, path)
            if mode == "read":
                read_count += 1
            else:
                write_count += 1
            target = value.get("target")
            if target not in TARGETS:
                self._error("VALUE.ENUM", f"{path}.target", "unsupported logical target")
            elif target in seen_targets:
                self._error("TOPOLOGY.DUPLICATE_TARGET", f"{path}.target", f"target {target} already has a stream")
            else:
                seen_targets.append(target)
            self._validate_base_addr(value.get("base_addr"), f"{path}.base_addr")
            self._validate_stream_index_fields(value, path)
            self._validate_bounds(value, path, "tailing")
            if mode == "read":
                self._validate_bounds(value, path, "padding")
                self._uint(value.get("padding_reg_value"), 8, f"{path}.padding_reg_value", nullable=True)
                if any(value.get("padding_enable", [])) and value.get("padding_reg_value") is None:
                    self._error("STREAM.PADDING_VALUE", f"{path}.padding_reg_value", "enabled padding requires an explicit byte value")
                self._uint(value.get("buf_full_last_index"), 4, f"{path}.buf_full_last_index")
            spatial_size = value.get("buf_spatial_size")
            if not isinstance(spatial_size, int) or isinstance(spatial_size, bool) or not 1 <= spatial_size <= 16:
                self._error("STREAM.SPATIAL_SIZE", f"{path}.buf_spatial_size", "must be in 1..16 so the terminal flag reaches a valid lane")
            strides = value.get("buf_spatial_stride")
            if not isinstance(strides, list) or not isinstance(spatial_size, int) or len(strides) != spatial_size:
                self._error("STREAM.SPATIAL_ARITY", f"{path}.buf_spatial_stride", "length must equal buf_spatial_size (native encoder pads the remaining lanes)")
            elif len(set(strides)) != len(strides):
                self._error("STREAM.SPATIAL_ALIAS", f"{path}.buf_spatial_stride", "enabled spatial lanes must not alias")
            if isinstance(strides, list):
                for index, item in enumerate(strides):
                    self._uint(item, 5, f"{path}.buf_spatial_stride[{index}]")
            ping_pong = value.get("ping_pong")
            self._uint(ping_pong, 1, f"{path}.ping_pong")
            self._uint(value.get("pingpong_last_index"), 4, f"{path}.pingpong_last_index", nullable=True)
            if ping_pong == 1 and value.get("pingpong_last_index") is None:
                self._error(
                    "STREAM.PINGPONG_THRESHOLD",
                    f"{path}.pingpong_last_index",
                    "enabled Buffer AG ping-pong requires an inclusive terminal threshold",
                )
            remap = value.get("address_remapping")
            if remap is not None and (
                not isinstance(remap, list) or len(remap) != 26 or sorted(remap) != list(range(26))
            ):
                self._error("STREAM.REMAP", f"{path}.address_remapping", "must be null or a permutation of 0..25")
            streams[name] = value
        if read_count > self.profile.read_streams:
            self._error("RESOURCE.LIMIT", "$.stream_engine", "more than four read streams")
        if write_count > self.profile.write_streams:
            self._error("RESOURCE.LIMIT", "$.stream_engine", "more than one write stream")
        self._facts["streams"] = {"read": read_count, "write": write_count, "targets": seen_targets}
        return streams

    def _validate_stream_index_fields(self, stream: Mapping[str, Any], path: str) -> None:
        sizes = self._list(stream.get("idx_size"), 3, f"{path}.idx_size")
        strides = self._list(stream.get("dim_stride"), 3, f"{path}.dim_stride")
        if sizes is not None:
            dims: list[int] = []
            for index, item in enumerate(sizes):
                if self._uint(item, 8, f"{path}.idx_size[{index}]", nullable=True):
                    dims.append(1 if item is None else item + 1)
            if len(dims) == 3:
                if any(dim & (dim - 1) for dim in dims):
                    self._error("STREAM.NON_POWER_OF_TWO", f"{path}.idx_size", "each idx_size+1 must be a power of two for idx_size_log")
                total = math.prod(dims)
                if not 1 <= total <= 255:
                    self._error("STREAM.TOTAL_SIZE", f"{path}.idx_size", f"derived total_size={total} does not fit the 8-bit nonzero domain")
        if strides is not None:
            for index, item in enumerate(strides):
                self._uint(item, 20, f"{path}.dim_stride[{index}]", nullable=True)
        mem_modes = self._list(
            stream.get("mem_idx_mode"), 3, f"{path}.mem_idx_mode"
        )
        if mem_modes is not None:
            for index, mode in enumerate(mem_modes):
                if mode not in INDEX_MODES:
                    self._error(
                        "VALUE.ENUM",
                        f"{path}.mem_idx_mode[{index}]",
                        "mode must be null/buffer/keep/constant; legacy integer 0 requires an explicit encoding-equivalent strict materialization",
                    )
            if mem_modes.count("buffer") != 1:
                self._error(
                    "TAG.CARRIER_COUNT",
                    f"{path}.mem_idx_mode",
                    "requires exactly one buffer-mode terminal-tag carrier",
                )

        buf_modes = self._list(
            stream.get("buf_idx_mode"), 2, f"{path}.buf_idx_mode"
        )
        if buf_modes is not None:
            for index, mode in enumerate(buf_modes):
                if mode not in {"buffer", "keep"}:
                    self._error(
                        "STREAM.BUFFER_INDEX_MODE",
                        f"{path}.buf_idx_mode[{index}]",
                        "Buffer AG has only buffer=0 and keep=1; null/constant would silently encode as buffer",
                    )
            if buf_modes.count("buffer") != 1:
                self._error(
                    "TAG.CARRIER_COUNT",
                    f"{path}.buf_idx_mode",
                    "requires exactly one buffer-mode terminal-tag carrier",
                )
        for field_name, length, width in (
            ("mem_idx_keep_last_index", 3, 4),
            ("buf_idx_keep_last_index", 2, 4),
            ("mem_idx_constant", 3, 8),
        ):
            values = self._list(stream.get(field_name), length, f"{path}.{field_name}")
            if values is not None:
                for index, item in enumerate(values):
                    self._uint(item, width, f"{path}.{field_name}[{index}]", nullable=True)
        indexes = self._list(stream.get("idx"), 3, f"{path}.idx")
        if indexes is not None:
            for index, item in enumerate(indexes):
                if item is not None and not isinstance(item, (str, int)):
                    self._error("VALUE.SOURCE", f"{path}.idx[{index}]", "must be null, a source name, or an integer")
        constants = stream.get("mem_idx_constant")
        if (
            mem_modes is not None
            and indexes is not None
            and isinstance(constants, list)
            and len(constants) == 3
        ):
            for index, (mode, source, constant) in enumerate(
                zip(mem_modes, indexes, constants, strict=True)
            ):
                if mode not in INDEX_MODES:
                    continue
                if mode in {"buffer", "keep"} and source is None:
                    self._error(
                        "STREAM.INDEX_SOURCE_REQUIRED",
                        f"{path}.idx[{index}]",
                        f"{mode} mode requires a selected source",
                    )
                elif mode in {None, "constant"} and source is not None:
                    self._error(
                        "STREAM.UNUSED_INDEX_SOURCE",
                        f"{path}.idx[{index}]",
                        f"{mode or 'null'} mode ignores the source selector",
                    )
                if mode == "constant" and constant is None:
                    self._error(
                        "STREAM.INDEX_CONSTANT_REQUIRED",
                        f"{path}.mem_idx_constant[{index}]",
                        "constant mode requires an explicit 8-bit raw pattern",
                    )
                elif mode != "constant" and constant is not None:
                    self._error(
                        "STREAM.UNUSED_INDEX_CONSTANT",
                        f"{path}.mem_idx_constant[{index}]",
                        f"{mode or 'null'} mode ignores the constant field",
                    )

    def _validate_bounds(self, stream: Mapping[str, Any], path: str, kind: str) -> None:
        if kind == "padding":
            enable_name, range_name, low_name, up_name = "padding_enable", "idx_padding_range", "low_bound", "up_bound"
        else:
            enable_name, range_name, low_name, up_name = "tailing_enable", "idx_tailing_range", "low", "up"
        enabled = stream.get(enable_name)
        self._bits(enabled, 3, f"{path}.{enable_name}")
        ranges = self._exact_keys(stream.get(range_name), {low_name, up_name}, f"{path}.{range_name}")
        if not isinstance(enabled, list) or len(enabled) != 3 or ranges is None:
            return
        lows = self._list(ranges.get(low_name), 3, f"{path}.{range_name}.{low_name}")
        ups = self._list(ranges.get(up_name), 3, f"{path}.{range_name}.{up_name}")
        if lows is None or ups is None:
            return
        for index, (flag, low, up) in enumerate(zip(enabled, lows, ups, strict=True)):
            if flag:
                low_ok = self._uint(low, 12, f"{path}.{range_name}.{low_name}[{index}]")
                up_ok = self._uint(up, 12, f"{path}.{range_name}.{up_name}[{index}]")
                if low_ok and up_ok and low > up:
                    self._error("STREAM.BOUNDS_ORDER", f"{path}.{range_name}[{index}]", "enabled inclusive range requires low <= up")
            elif low is not None or up is not None:
                self._error("STREAM.DISABLED_BOUNDS", f"{path}.{range_name}[{index}]", "disabled dimension must use null bounds")

    def _validate_base_addr(self, value: Any, path: str) -> None:
        parsed: int | None = None
        if isinstance(value, int) and not isinstance(value, bool):
            parsed = value
        elif isinstance(value, str):
            compact = value.strip().replace("_", "")
            if compact.lower().startswith("0b") and len(compact[2:]) == 30 and not set(compact[2:]) - {"0", "1"}:
                parsed = int(compact[2:], 2)
            elif compact.lower().startswith("0x"):
                try:
                    parsed = int(compact, 16)
                except ValueError:
                    parsed = None
        if parsed is None or isinstance(parsed, bool) or not 0 <= parsed < (1 << 30):
            self._error("ADDRESS.PARSE", path, "must be an integer, exact 30-bit 0b literal, or 0x literal in range")
            return
        if parsed & 0xF:
            self._error("ADDRESS.ALIGNMENT", path, "low four subword bits must be zero; RTL base addition discards them")
        row = (parsed >> 10) & 0x1FFF
        if row >= self.profile.ddr_rows:
            self._error("ADDRESS.ROW", path, f"row={row} exceeds target row limit {self.profile.ddr_rows}")

    def _validate_buffers(
        self, raw: Any
    ) -> dict[str, Mapping[str, Any]]:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.buffer_config", "must be an object")
            return {}
        if len(raw) > self.profile.buffers:
            self._error("RESOURCE.LIMIT", "$.buffer_config", "hardware has six buffers")
        buffers: dict[str, Mapping[str, Any]] = {}
        required = {"nbr_enable", "buf_full_last_index", "dst_port", "buffer_life_time", "mode", "mask", "buf_end_row_addr"}
        allowed = required | {"enable", "buffer_nbr_cnt"}
        for name, value in raw.items():
            path = f"$.buffer_config.{name}"
            if not re.fullmatch(r"buffer[0-5]", name):
                self._error("RESOURCE.NAME", path, "must be buffer0..buffer5")
            if not isinstance(value, Mapping):
                self._error("SCHEMA.TYPE", path, "must be an object")
                continue
            for key in sorted(required - set(value)):
                self._error("SCHEMA.MISSING_FIELD", f"{path}.{key}", "required field is missing")
            for key in sorted(set(value) - allowed):
                self._error("SCHEMA.UNKNOWN_FIELD", f"{path}.{key}", "field is not encoded by BufferConfig")
            if "enable" in value:
                self._uint(value.get("enable"), 1, f"{path}.enable")
            for field_name, width in (("nbr_enable", 1), ("buf_full_last_index", 4), ("dst_port", 1), ("mode", 1), ("buf_end_row_addr", 2)):
                self._uint(value.get(field_name), width, f"{path}.{field_name}")
            lifetime = value.get("buffer_life_time")
            if not isinstance(lifetime, int) or isinstance(lifetime, bool) or not 1 <= lifetime <= 16:
                self._error("BUFFER.LIFETIME", f"{path}.buffer_life_time", "logical lifetime must be 1..16 before x-1 encoding")
            self._bits(value.get("mask"), 8, f"{path}.mask")
            self._uint(value.get("buffer_nbr_cnt"), 5, f"{path}.buffer_nbr_cnt", nullable=True)
            buffers[name] = value
        return buffers

    def _validate_buffer_topology(
        self,
        config: Mapping[str, Any],
        streams: Mapping[str, Mapping[str, Any]],
        buffers: Mapping[str, Mapping[str, Any]],
    ) -> None:
        read_target_buffer = {
            "A": "buffer0",
            "B": "buffer2",
            "B'": "buffer3",
            "C": "buffer4",
            "D": "buffer4",
        }
        for stream_name, stream in streams.items():
            mode = stream.get("mode")
            target = stream.get("target")
            mapped_name = (
                "buffer5"
                if mode == "write"
                else read_target_buffer.get(str(target))
            )
            stream_path = f"$.stream_engine.{stream_name}"
            mapped = buffers.get(mapped_name) if mapped_name else None
            if not isinstance(mapped, Mapping):
                self._error(
                    "BUFFER.MAPPED_INSTANCE_REQUIRED",
                    stream_path,
                    f"physical stream path requires enabled {mapped_name}",
                )
                continue
            if mapped.get("enable", 1) != 1:
                self._error(
                    "BUFFER.MAPPED_INSTANCE_DISABLED",
                    f"$.buffer_config.{mapped_name}.enable",
                    f"{stream_name} references this physical buffer",
                )
            if (
                mode == "read"
                and stream.get("buf_full_last_index")
                != mapped.get("buf_full_last_index")
            ):
                self._error(
                    "BUFFER.FULL_THRESHOLD_MISMATCH",
                    f"{stream_path}.buf_full_last_index",
                    (
                        "read-stream and mapped Buffer Manager use independent "
                        "inclusive full thresholds and strict targets require equality"
                    ),
                )
            if stream.get("ping_pong") == 1:
                if mode != "read" or target != "A":
                    self._error(
                        "BUFFER.PINGPONG_TOPOLOGY",
                        f"{stream_path}.ping_pong",
                        (
                            "only target A / physical READ_STREAM0 has a real "
                            "buffer0-buffer1 pair"
                        ),
                    )
                pair = buffers.get("buffer1")
                if not isinstance(pair, Mapping):
                    self._error(
                        "BUFFER.PINGPONG_PAIR_REQUIRED",
                        "$.buffer_config.buffer1",
                        "enabled READ_STREAM0 ping-pong requires buffer1",
                    )
                elif buffers.get("buffer0") != pair:
                    self._error(
                        "BUFFER.PINGPONG_PAIR_MISMATCH",
                        "$.buffer_config.buffer1",
                        (
                            "buffer0 and buffer1 must have identical strict "
                            "configuration for alternating requests"
                        ),
                    )

        buffer5 = buffers.get("buffer5")
        if isinstance(buffer5, Mapping):
            has_sa = isinstance(config.get("special_array"), Mapping)
            has_ga = isinstance(config.get("general_array"), Mapping)
            source = buffer5.get("dst_port")
            if has_sa and not has_ga and source != 0:
                self._error(
                    "BUFFER.ARRAY_SOURCE",
                    "$.buffer_config.buffer5.dst_port",
                    "buffer5 source selector must be 0 for Specialized Array",
                )
            if has_ga and not has_sa and source != 1:
                self._error(
                    "BUFFER.ARRAY_SOURCE",
                    "$.buffer_config.buffer5.dst_port",
                    "buffer5 source selector must be 1 for General Array",
                )

    def _validate_n2n(
        self,
        raw: Any,
        buffers: Mapping[str, Mapping[str, Any]],
    ) -> None:
        if not isinstance(raw, Mapping):
            self._error("SCHEMA.TYPE", "$.n2n", "must be an object")
            return
        if len(raw) > 2:
            self._error("RESOURCE.LIMIT", "$.n2n", "hardware has two neighbor streams")
        stream_facts: dict[str, Any] = {}
        for name, value in raw.items():
            path = f"$.n2n.{name}"
            if not re.fullmatch(r"neighbor_stream[01]", name):
                self._error("RESOURCE.NAME", path, "must be neighbor_stream0 or neighbor_stream1")
            item = self._exact_keys(value, {"mem_loop", "src_slice_sel", "dst_slice_sel", "ping_pong"}, path)
            if item is None:
                continue
            mem_loop = item.get("mem_loop")
            if not isinstance(mem_loop, int) or isinstance(mem_loop, bool) or not 1 <= mem_loop <= 32:
                self._error("N2N.MEM_LOOP", f"{path}.mem_loop", "logical neighbor count must be 1..32 before x-1 encoding")
            self._uint(item.get("src_slice_sel"), 1, f"{path}.src_slice_sel")
            self._uint(item.get("dst_slice_sel"), 1, f"{path}.dst_slice_sel")
            self._uint(item.get("ping_pong"), 1, f"{path}.ping_pong")
            if item.get("ping_pong") == 0:
                self._error(
                    "N2N.PINGPONG_HARDWIRED",
                    f"{path}.ping_pong",
                    (
                        "the decoded bit is not connected; RTL always alternates "
                        "the physical source/destination buffer pair"
                    ),
                )

            stream_index = int(name[-1]) if re.fullmatch(r"neighbor_stream[01]", name) else 0
            pair_names = (f"buffer{2 * stream_index}", f"buffer{2 * stream_index + 1}")
            pair = [buffers.get(buffer_name) for buffer_name in pair_names]
            for buffer_name, buffer in zip(pair_names, pair, strict=True):
                buffer_path = f"$.buffer_config.{buffer_name}"
                if not isinstance(buffer, Mapping):
                    self._error(
                        "N2N.BUFFER_PAIR_REQUIRED",
                        buffer_path,
                        f"{name} requires both physical buffers {pair_names[0]}/{pair_names[1]}",
                    )
                    continue
                if buffer.get("enable", 1) != 1 or buffer.get("nbr_enable") != 1:
                    self._error(
                        "N2N.BUFFER_NEIGHBOR_DISABLED",
                        buffer_path,
                        f"{name} can transfer only through an enabled neighbor buffer pair",
                    )
                if buffer.get("buf_end_row_addr") != 3:
                    self._error(
                        "N2N.FULL_ROW_REQUIRED",
                        f"{buffer_path}.buf_end_row_addr",
                        "N2N controller always reads/writes rows 0..3",
                    )

            if all(isinstance(buffer, Mapping) for buffer in pair):
                normalized_pair = []
                for buffer in pair:
                    assert isinstance(buffer, Mapping)
                    normalized_pair.append(
                        {
                            "enable": buffer.get("enable", 1),
                            "nbr_enable": buffer.get("nbr_enable"),
                            "buf_full_last_index": buffer.get("buf_full_last_index"),
                            "buffer_nbr_cnt": buffer.get("buffer_nbr_cnt", 27),
                            "buffer_life_time": buffer.get("buffer_life_time"),
                            "mode": buffer.get("mode"),
                            "mask": buffer.get("mask"),
                            "buf_end_row_addr": buffer.get("buf_end_row_addr"),
                        }
                    )
                if normalized_pair[0] != normalized_pair[1]:
                    self._error(
                        "N2N.BUFFER_PAIR_MISMATCH",
                        f"$.buffer_config.{pair_names[1]}",
                        (
                            "hard-wired alternation requires the physical N2N "
                            "buffer pair to have identical active configuration"
                        ),
                    )

            stream_facts[name] = {
                "encoded_nse_cnt_size": (
                    mem_loop - 1
                    if isinstance(mem_loop, int) and not isinstance(mem_loop, bool)
                    else None
                ),
                "material_transfer_count": (
                    mem_loop - 1
                    if isinstance(mem_loop, int) and not isinstance(mem_loop, bool)
                    else None
                ),
                "src_ring": "low_28_slice" if item.get("src_slice_sel") == 0 else "high_4_slice",
                "dst_ring": "low_28_slice" if item.get("dst_slice_sel") == 0 else "high_4_slice",
                "physical_buffer_pair": list(pair_names),
                "rows_per_transfer": [0, 1, 2, 3],
            }
        if stream_facts:
            self._facts["n2n"] = {
                "streams": stream_facts,
                "ping_pong_json_controls_hardware": False,
                "hardware_alternates_buffer_pairs": True,
                "nse_enable_auto_clears_after_completion": False,
                "handoff": "material four-row buffer copy/rotation, not zero-copy",
            }

    def _validate_sa(
        self,
        raw: Any,
        *,
        development_mode: bool,
        expected_sa_transpose: bool | None,
    ) -> None:
        if raw is None:
            return
        path = "$.special_array"
        sa = self._exact_keys(raw, {"mode", "bias_enable", "data_type", "transout_last_index", "inport0", "inport1", "inport2", "outport"}, path)
        if sa is None:
            return
        if sa.get("mode") not in {"gemm", "gemv"}:
            self._error("VALUE.ENUM", f"{path}.mode", "must be gemm or gemv; unknown strings must not fall through to gemv")
        if sa.get("data_type") not in {"int8", "fp16", "bf16"}:
            self._error("VALUE.ENUM", f"{path}.data_type", "unsupported SA datatype")
        bias_enable = sa.get("bias_enable")
        self._uint(bias_enable, 1, f"{path}.bias_enable")
        self._uint(sa.get("transout_last_index"), 4, f"{path}.transout_last_index")
        ports: list[Mapping[str, Any] | None] = []
        for index in range(3):
            pp = f"{path}.inport{index}"
            port = self._exact_keys(sa.get(f"inport{index}"), {"enable", "pingpong_en", "pingpong_last_index", "nbr_enable"}, pp)
            ports.append(port)
            if port is None:
                continue
            for field_name in ("enable", "pingpong_en", "nbr_enable"):
                self._uint(port.get(field_name), 1, f"{pp}.{field_name}")
            self._uint(port.get("pingpong_last_index"), 4, f"{pp}.pingpong_last_index", nullable=True)
            if port.get("pingpong_en") == 1 and port.get("pingpong_last_index") is None:
                self._error(
                    "SA.PINGPONG_THRESHOLD_REQUIRED",
                    f"{pp}.pingpong_last_index",
                    "enabled SA ping-pong requires an explicit inclusive last-index threshold",
                )
            if port.get("enable") == 0 and (
                port.get("pingpong_en") != 0
                or port.get("nbr_enable") != 0
                or port.get("pingpong_last_index") is not None
            ):
                self._error(
                    "SA.DISABLED_INPORT_FIELDS",
                    pp,
                    "disabled SA inport must clear ping-pong, neighbor and threshold fields",
                )
        for index in (0, 1):
            if isinstance(ports[index], Mapping) and ports[index].get("enable") != 1:
                self._error(
                    "SA.OPERAND_INPORT_REQUIRED",
                    f"{path}.inport{index}.enable",
                    "SA MAC operand inports 0 and 1 must be enabled",
                )
        inport2 = ports[2]
        if isinstance(inport2, Mapping):
            if inport2.get("pingpong_en") != 0:
                self._error(
                    "SA.INPORT2_PINGPONG_TOPOLOGY",
                    f"{path}.inport2.pingpong_en",
                    "inport2 source1 is hard zero; physical buffer4 has no ping-pong pair",
                )
            if bias_enable == 1 and inport2.get("enable") != 1:
                self._error(
                    "SA.BIAS_INPORT_REQUIRED",
                    f"{path}.inport2.enable",
                    "bias_enable=1 requires inport2/buffer4",
                )
            if bias_enable == 0 and inport2.get("enable") != 0:
                self._error(
                    "SA.BIAS_INPORT_DISABLED",
                    f"{path}.inport2.enable",
                    "bias_enable=0 must use the RTL zero seed and disable inport2",
                )
        if sa.get("data_type") == "int8":
            self._facts["sa_int8_mac"] = {
                "data_a": "four signed int8 lanes",
                "data_b": "four unsigned uint8 lanes",
                "psum": "32-bit accumulator pattern",
                "current_rtl_equation": (
                    "psum + signext(CSA4.sum17) + "
                    "(signext(CSA4.carry17_already_shifted)<<1) mod 2^32"
                ),
                "conventional_four_lane_dot_equivalent": False,
                "classification": "CONTRADICTED",
            }
        out = self._exact_keys(sa.get("outport"), {"mode", "fp32tofp16", "fp32tobf16"}, f"{path}.outport")
        if out is None:
            return
        label = out.get("mode")
        if label not in SA_LABEL_TO_ENCODED_MAJOR:
            self._error("VALUE.ENUM", f"{path}.outport.mode", "must be row or col")
            return
        bit = SA_LABEL_TO_ENCODED_MAJOR[label]
        actual_transpose = bool(bit)
        fp16 = self._boolean_flag(out.get("fp32tofp16"), f"{path}.outport.fp32tofp16")
        bf16 = self._boolean_flag(out.get("fp32tobf16"), f"{path}.outport.fp32tobf16")
        if fp16 and bf16:
            self._error("SA.CONVERSION_CONFLICT", f"{path}.outport", "fp32tofp16 and fp32tobf16 are mutually exclusive")
        self._facts["sa_layout"] = {
            "legacy_label": label,
            "encoded_major_bit": bit,
            "physical_transpose": actual_transpose,
            "rtl_assignment": "bit0=preserve[out][source], bit1=input[source][out]",
        }
        if development_mode and expected_sa_transpose is None:
            self._error("SA.LAYOUT_CONTRACT_REQUIRED", f"{path}.outport.mode", "development mode requires expected_sa_transpose from the operator layout contract")
        elif expected_sa_transpose is not None and actual_transpose != expected_sa_transpose:
            self._error("SA.LAYOUT_MISMATCH", f"{path}.outport.mode", f"encoded physical_transpose={actual_transpose} conflicts with contract={expected_sa_transpose}")

    def _boolean_flag(self, value: Any, path: str) -> bool | None:
        if value in (True, "true"):
            return True
        if value in (False, "false"):
            return False
        self._error("VALUE.BOOLEAN", path, "must be true/false or 'true'/'false'")
        return None

    def _validate_ga(self, raw: Any) -> None:
        if raw is None:
            return
        ga = self._exact_keys(raw, {"inport", "outport", "PE_array"}, "$.general_array")
        if ga is None:
            return
        inports = ga.get("inport")
        if not isinstance(inports, Mapping):
            self._error("SCHEMA.TYPE", "$.general_array.inport", "must be an object")
        else:
            if len(inports) > 3:
                self._error("RESOURCE.LIMIT", "$.general_array.inport", "hardware has three GA inports")
            keys = {"mask", "src_id", "pingpong_en", "pingpong_last_index", "nbr_enable", "fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32"}
            inport_facts: dict[str, Any] = {}
            for name, value in inports.items():
                path = f"$.general_array.inport.{name}"
                if not re.fullmatch(r"inport[0-2]", name):
                    self._error("RESOURCE.NAME", path, "must be inport0..inport2")
                port = self._exact_keys(value, keys, path)
                if port is None:
                    continue
                self._bits(port.get("mask"), 8, f"{path}.mask")
                self._uint(port.get("src_id"), 1, f"{path}.src_id")
                self._uint(port.get("pingpong_en"), 1, f"{path}.pingpong_en")
                self._uint(port.get("pingpong_last_index"), 4, f"{path}.pingpong_last_index", nullable=True)
                self._uint(port.get("nbr_enable"), 1, f"{path}.nbr_enable")
                conversions = [self._boolean_flag(port.get(field_name), f"{path}.{field_name}") for field_name in ("fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32")]
                if sum(item is True for item in conversions) > 1:
                    self._error("GA.CONVERSION_CONFLICT", path, "at most one input conversion may be enabled")
                if port.get("pingpong_en") == 1 and port.get("pingpong_last_index") is None:
                    self._error(
                        "GA.PINGPONG_THRESHOLD_REQUIRED",
                        f"{path}.pingpong_last_index",
                        "enabled GA ping-pong requires an inclusive last-index threshold",
                    )
                if port.get("pingpong_en") == 0 and port.get("pingpong_last_index") is not None:
                    self._error(
                        "GA.UNUSED_PINGPONG_THRESHOLD",
                        f"{path}.pingpong_last_index",
                        "threshold is consumed only when GA ping-pong is enabled",
                    )
                if port.get("src_id") == 1 and port.get("pingpong_en") == 1:
                    self._error(
                        "GA.PINGPONG_SOURCE",
                        path,
                        (
                            "src_id=1 is the single SA-result source; it has no "
                            "second physical source for ping-pong"
                        ),
                    )
                enabled_conversion = next(
                    (
                        field_name
                        for field_name, enabled in zip(
                            ("fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32"),
                            conversions,
                            strict=True,
                        )
                        if enabled is True
                    ),
                    None,
                )
                inport_facts[name] = {
                    "src0": "physical_buffer_pair",
                    "src1": "SA_outport_source0",
                    "conversion": enabled_conversion,
                    "serialization": (
                        "low16_then_high16"
                        if enabled_conversion in {"fp16tofp32", "bf16tofp32"}
                        else "bytes_low_to_high"
                        if enabled_conversion in {"uint8tofp32", "uint8toint32"}
                        else "one_word"
                    ),
                }
                if enabled_conversion == "int32tofp32":
                    self._facts["ga_int32tofp32"] = {
                        "classification": "CONTRADICTED",
                        "minus_one_rtl_bits": "0xcf000000",
                        "int_min_rtl_bits": "0xce800000",
                        "general_signed_conversion_equivalent": False,
                    }
            if inport_facts:
                self._facts["ga_inports"] = inport_facts
        out = self._exact_keys(ga.get("outport"), {"mask", "src_id", "fp32tofp16", "fp32tobf16", "int32touint8"}, "$.general_array.outport")
        if out is not None:
            self._bits(out.get("mask"), 8, "$.general_array.outport.mask")
            self._uint(out.get("src_id"), 1, "$.general_array.outport.src_id")
            conversions = [self._boolean_flag(out.get(field_name), f"$.general_array.outport.{field_name}") for field_name in ("fp32tofp16", "fp32tobf16", "int32touint8")]
            if sum(item is True for item in conversions) > 1:
                self._error("GA.CONVERSION_CONFLICT", "$.general_array.outport", "at most one output conversion may be enabled")
        pes = ga.get("PE_array")
        if not isinstance(pes, Mapping):
            self._error("SCHEMA.TYPE", "$.general_array.PE_array", "must be an object")
        elif len(pes) > 16:
            self._error("RESOURCE.LIMIT", "$.general_array.PE_array", "hardware has a 4x4 GA")
        else:
            pe_facts: dict[str, Any] = {}
            for name, value in pes.items():
                path = f"$.general_array.PE_array.{name}"
                if not re.fullmatch(r"PE[0-3][0-3]", name):
                    self._error("RESOURCE.NAME", path, "must be PE00..PE33")
                pe = self._exact_keys(value, {"alu_opcode", "transout_last_index", "inport0", "inport1", "inport2"}, path)
                if pe is None:
                    continue
                opcode = pe.get("alu_opcode")
                if opcode not in GA_OPCODES:
                    self._error("GA.OPCODE", f"{path}.alu_opcode", "unsupported GA opcode")
                self._uint(pe.get("transout_last_index"), 4, f"{path}.transout_last_index", nullable=True)
                modes: list[Any] = []
                for index in range(3):
                    modes.append(
                        self._validate_compute_port(
                            pe.get(f"inport{index}"),
                            f"{path}.inport{index}",
                            32,
                        )
                    )
                used_ports = GA_OPERAND_PORTS.get(opcode, set())
                for index, mode in enumerate(modes):
                    if index in used_ports and mode is None:
                        self._error(
                            "GA.OPERAND_DISABLED",
                            f"{path}.inport{index}.mode",
                            f"{opcode} consumes inport{index}; null disables its RTL valid gate",
                        )
                pe_match = re.fullmatch(r"PE([0-3])([0-3])", name)
                pe_column = int(pe_match.group(2)) if pe_match else None
                if opcode in GA_SFU_OPCODES and pe_column not in {1, 3}:
                    self._error(
                        "GA.SFU_PLACEMENT",
                        f"{path}.alu_opcode",
                        "only odd GA columns 1 and 3 instantiate GA_SFU_PE",
                    )
                pe_facts[name] = {
                    "opcode": opcode,
                    "required_operands": sorted(used_ports),
                    "enabled_nonnumeric_operands": [
                        index
                        for index, mode in enumerate(modes)
                        if index not in used_ports and mode is not None
                    ],
                    "enabled_nonnumeric_effect": (
                        "still participates in input matching/backpressure"
                    ),
                    "sfu_capable_column": pe_column in {1, 3},
                }
                if opcode == "int8_max":
                    self._facts["ga_int8_max"] = {
                        "classification": "CONTRADICTED",
                        "numeric_equation": "unsigned bytewise min(A,C), not max(A,C)",
                        "pipeline0_accepts_second_item": False,
                    }
            if pe_facts:
                self._facts["ga_pes"] = pe_facts

    def _validate_terminal_chain(
        self,
        config: Mapping[str, Any],
        streams: Mapping[str, Mapping[str, Any]],
    ) -> None:
        writes = [(name, stream) for name, stream in streams.items() if stream.get("mode") == "write" and stream.get("target") == "D"]
        groups = [(name, group) for name, group in config.get("buffer_loop_configs", {}).items() if isinstance(group, Mapping) and group.get("target") == "D"] if isinstance(config.get("buffer_loop_configs", {}), Mapping) else []
        if len(writes) != 1:
            self._error("COMPLETION.WRITE_D_COUNT", "$.stream_engine", f"requires exactly one write target D, found {len(writes)}")
            return
        if len(groups) != 1:
            self._error("COMPLETION.GROUP_D_COUNT", "$.buffer_loop_configs", f"requires exactly one buffer-loop target D, found {len(groups)}")
            return
        stream_name, stream = writes[0]
        group_name, _ = groups[0]
        modes = stream.get("buf_idx_mode")
        if not isinstance(modes, list) or len(modes) != 2 or modes.count("buffer") != 1:
            return
        carrier_kind = "ROW_LC" if modes.index("buffer") == 0 else "COL_LC"
        carrier = f"{group_name}.{carrier_kind}"
        tags = self._possible_last_indices(config, carrier, set())
        self._facts["completion"] = {
            "write_stream": stream_name,
            "write_target": "D",
            "buffer_tag_carrier": carrier,
            "possible_last_indices": sorted(tags),
            "terminal_condition": "last=1 && last_index=0, then final DDR write-data handshake",
        }
        if 0 not in tags:
            self._error("COMPLETION.NO_TERMINAL_ZERO", f"$.stream_engine.{stream_name}.buf_idx_mode", f"carrier {carrier} cannot produce last_index=0")
        spatial_size = stream.get("buf_spatial_size")
        if isinstance(spatial_size, int) and not 1 <= spatial_size <= 16:
            self._error("COMPLETION.TERMINAL_LANE", f"$.stream_engine.{stream_name}.buf_spatial_size", "terminal flag would miss the valid 16-lane bitmap")

    def _possible_last_indices(
        self,
        config: Mapping[str, Any],
        source: Any,
        visiting: set[str],
    ) -> set[int]:
        if not isinstance(source, str):
            self._error("GRAPH.MISSING_SOURCE", "$", f"terminal carrier source is not named: {source!r}")
            return set()
        if source in visiting:
            self._error("GRAPH.CYCLE", "$", f"cycle in terminal-tag graph at {source}")
            return set()
        visiting = set(visiting)
        visiting.add(source)
        if source.startswith("DRAM_LC."):
            name = source.split(".", 1)[1]
            loop = config.get("dram_loop_configs", {}).get(name) if isinstance(config.get("dram_loop_configs"), Mapping) else None
            if not isinstance(loop, Mapping):
                self._error("GRAPH.MISSING_SOURCE", "$", f"missing {source}")
                return set()
            own = loop.get("last_index")
            result = {own} if isinstance(own, int) and 0 <= own <= 15 else set()
            upstream = loop.get("src_id")
            if upstream is None:
                if loop.get("outmost_loop") != 1:
                    self._error("GRAPH.ROOT_NOT_OUTMOST", f"$.dram_loop_configs.{name}", "root of an active terminal chain must be outmost_loop=1")
                    return set()
                return result
            return result | self._possible_last_indices(config, upstream, visiting)
        if source.startswith("LC_PE."):
            name = source.split(".", 1)[1]
            pe = config.get("lc_pe_configs", {}).get(name) if isinstance(config.get("lc_pe_configs"), Mapping) else None
            if not isinstance(pe, Mapping):
                self._error("GRAPH.MISSING_SOURCE", "$", f"missing {source}")
                return set()
            ports = [pe.get(f"inport{index}") for index in range(3)]
            carriers = [port for port in ports if isinstance(port, Mapping) and port.get("mode") == "buffer"]
            if len(carriers) != 1:
                self._error("TAG.CARRIER_COUNT", f"$.lc_pe_configs.{name}", "terminal graph requires exactly one buffer carrier")
                return set()
            return self._possible_last_indices(config, carriers[0].get("src_id"), visiting)
        match = re.fullmatch(r"(GROUP[0-4])\.(ROW_LC|COL_LC)", source)
        if match:
            group_name, kind = match.groups()
            group = config.get("buffer_loop_configs", {}).get(group_name) if isinstance(config.get("buffer_loop_configs"), Mapping) else None
            loop = group.get(kind) if isinstance(group, Mapping) else None
            if not isinstance(loop, Mapping):
                self._error("GRAPH.MISSING_SOURCE", "$", f"missing {source}")
                return set()
            own = loop.get("last_index")
            result = {own} if isinstance(own, int) and 0 <= own <= 15 else set()
            return result | self._possible_last_indices(config, loop.get("src_id"), visiting)
        self._error("GRAPH.UNKNOWN_SOURCE", "$", f"unsupported terminal source {source!r}")
        return set()

    def _validate_sa_pingpong(
        self,
        config: Mapping[str, Any],
        streams: Mapping[str, Mapping[str, Any]],
    ) -> None:
        sa = config.get("special_array")
        if not isinstance(sa, Mapping):
            return
        producers = {stream.get("target") for stream in streams.values() if stream.get("mode") == "read"}
        buffers = config.get("buffer_config")
        buffer_map = buffers if isinstance(buffers, Mapping) else {}
        bindings = (
            (0, {"A"}, ("buffer0", "buffer1"), "TOPOLOGY.SA_A_PINGPONG"),
            (1, {"B", "B'"}, ("buffer2", "buffer3"), "TOPOLOGY.SA_B_PINGPONG"),
        )
        for index, required_targets, pair, code in bindings:
            port = sa.get(f"inport{index}")
            if (
                not isinstance(port, Mapping)
                or port.get("enable") != 1
                or port.get("pingpong_en") != 1
            ):
                continue
            path = f"$.special_array.inport{index}"
            missing = sorted(required_targets - producers)
            if missing:
                self._error(
                    code,
                    path,
                    f"ping-pong input lacks producers: {missing}",
                )
            threshold = port.get("pingpong_last_index")
            for buffer_name in pair:
                buffer = buffer_map.get(buffer_name)
                if not isinstance(buffer, Mapping):
                    self._error(
                        "SA.PINGPONG_BUFFER_REQUIRED",
                        f"$.buffer_config.{buffer_name}",
                        f"{path} requires physical {buffer_name}",
                    )
                elif buffer.get("buf_full_last_index") != threshold:
                    self._error(
                        "SA.PINGPONG_THRESHOLD_MISMATCH",
                        f"$.buffer_config.{buffer_name}.buf_full_last_index",
                        (
                            f"must equal {path}.pingpong_last_index={threshold} "
                            "for the selected physical pair"
                        ),
                    )


def validate_sequence(
    configs: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    profile: TargetProfile | None = None,
    development_mode: bool = False,
    expected_sa_transpose: Mapping[str, bool] | None = None,
) -> list[ValidationReport]:
    state = ConfigState()
    reports: list[ValidationReport] = []
    contracts = expected_sa_transpose or {}
    for source, config in configs:
        report = OperatorConfigValidator(profile).validate(
            config,
            source=source,
            previous_state=state,
            development_mode=development_mode,
            expected_sa_transpose=contracts.get(source),
        )
        reports.append(report)
        state = report.next_state
    return reports


def load_json_configs(paths: Iterable[Path]) -> list[tuple[str, Mapping[str, Any]]]:
    loaded: list[tuple[str, Mapping[str, Any]]] = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError(f"{path} root must be an object")
        loaded.append((str(path), value))
    return loaded
