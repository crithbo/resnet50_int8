from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
import re
import struct
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from .operator_config_validator import TargetProfile, ValidationIssue


COMMAND_RE = re.compile(r"^\s*(\d+)\s+<([01]{64})>\s+(.*)$")
LOAD_RE = re.compile(r"^Load_Config(?: SFU)? for operator ([^ ]+)")
START_RE = re.compile(r"^Start_Comp for operator ([^ ]+)")
EXPLAINED_INT_RE = {
    "slice": re.compile(r"(?:^|, )slice_bin=([01]{5})(?:,|$)"),
    "register": re.compile(r"(?:^|, )reg_addr_bin=([01]{14})(?:,|$)"),
    "value": re.compile(r"(?:^|, )write_value_hex=0x([0-9A-Fa-f]{8})(?:,|$)"),
}

DTYPE_BYTES = {
    "fp16": 2,
    "fp32": 4,
    "int8": 1,
    "uint8": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
}

RESOURCE_TARGET = {
    "READ_STREAM0": "A",
    "READ_STREAM1": "B",
    "READ_STREAM2": "B'",
    "READ_STREAM3": "C",
    "WRITE_STREAM0": "D",
}

STREAM_LAYOUT = {
    "read": {"section": "se_rd_mse", "slots": 4, "chunks": 10, "port_width": 58},
    "write": {"section": "se_wr_mse", "slots": 1, "chunks": 8, "port_width": 62},
}

READ_FIELD_WIDTHS = (
    ("mem_idx_mode", 6),
    ("mem_idx_keep_last_index", 12),
    ("idx", 15),
    ("mem_idx_constant", 24),
    ("buf_idx_mode", 2),
    ("buf_idx_keep_last_index", 8),
    ("ping_pong", 1),
    ("pingpong_last_index", 4),
    ("base_addr", 30),
    ("idx_size", 24),
    ("idx_size_log", 9),
    ("total_size", 8),
    ("dim_stride", 60),
    ("address_remapping", 130),
    ("padding_reg_value", 8),
    ("padding_enable", 3),
    ("idx_padding_range", 72),
    ("tailing_enable", 3),
    ("idx_tailing_range", 72),
    ("buf_spatial_stride", 80),
    ("buf_spatial_size", 5),
    ("buf_full_last_index", 4),
)

WRITE_FIELD_WIDTHS = (
    ("_padding", 3),
    ("mem_idx_mode", 6),
    ("mem_idx_keep_last_index", 12),
    ("idx", 15),
    ("mem_idx_constant", 24),
    ("buf_idx_mode", 2),
    ("buf_idx_keep_last_index", 8),
    ("ping_pong", 1),
    ("pingpong_last_index", 4),
    ("base_addr", 30),
    ("idx_size", 24),
    ("idx_size_log", 9),
    ("total_size", 8),
    ("dim_stride", 60),
    ("address_remapping", 130),
    ("tailing_enable", 3),
    ("idx_tailing_range", 72),
    ("buf_spatial_stride", 80),
    ("buf_spatial_size", 5),
)


@dataclass(frozen=True)
class RequestRegion:
    key: str
    target: str
    slice_id: int
    bank: int
    start: int
    end: int


@dataclass
class RequestAddressValidationReport:
    graph_root: str
    valid: bool
    issues: list[ValidationIssue]
    facts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "operator-config-request-address-validation-report-v1",
            "graph_root": self.graph_root,
            "valid": self.valid,
            "first_error": asdict(self.issues[0]) if self.issues else None,
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
        }


@dataclass
class _StreamState:
    resource: str
    mode: str
    bits: str
    initial_bits: str
    metadata: Mapping[str, Any]
    source_config: Mapping[str, Any]


@dataclass(frozen=True)
class _Instruction:
    index: int
    word: int
    kind: str
    explanation: str
    operator: str | None
    config_sfu: bool | None = None
    slice_id: int | None = None
    register: int | None = None
    value: int | None = None


class _IndexModelError(ValueError):
    pass


class OperatorConfigRequestAddressValidator:
    """Replay stream register writes and enumerate RTL memory requests.

    The implementation does not import ``ndp-sim``.  It consumes the emitted
    bitstream parse, mapping review, execplan and JSON as data, then mirrors the
    active RTL equations in RD/WR_Memory_AG: transaction byte bias, 16-byte
    transfer splitting, 26-bit permutation, and post-remap base addition.
    """

    def __init__(
        self,
        *,
        profile: TargetProfile | None = None,
        max_index_assignments: int = 1_000_000,
        include_request_rows: bool = True,
    ) -> None:
        self.profile = profile or TargetProfile()
        self.max_index_assignments = max_index_assignments
        self.include_request_rows = include_request_rows
        self._issues: list[ValidationIssue] = []

    def validate(
        self,
        graph_root: Path,
        *,
        graph_path: Path,
        source_configs: Mapping[str, Path],
    ) -> RequestAddressValidationReport:
        self._issues = []
        root = graph_root.resolve()
        graph_path = graph_path.resolve()
        graph = self._load_object(graph_path, "REQUEST.GRAPH_PARSE", "$.graph")
        operators, params = self._operators(graph)
        sca_entries = self._sca_entries(root)
        instructions = self._instructions(root)
        loads = [item for item in instructions if item.kind == "Load_Config" and item.config_sfu is False]
        starts = [item for item in instructions if item.kind == "Start_Comp"]

        if len(loads) != len(operators) or len(starts) != len(operators):
            self._error(
                "REQUEST.STAGE_COUNT",
                "$.execplan",
                "operator, non-SFU Load_Config, and Start_Comp counts must match",
            )

        runtime: dict[int, dict[str, _StreamState]] = {
            slice_id: {} for slice_id in range(self.profile.slices)
        }
        iga_config: dict[int, Mapping[str, Any] | None] = {
            slice_id: None for slice_id in range(self.profile.slices)
        }
        stage_facts: list[dict[str, Any]] = []
        request_total = 0
        unique_global: set[int] = set()

        for stage_index in range(min(len(operators), len(loads), len(starts))):
            operator = operators[stage_index]
            op_id = operator["id"]
            stage_path = f"$.stages[{stage_index}]"
            load, start = loads[stage_index], starts[stage_index]
            if load.operator != op_id or start.operator != op_id or not load.index < start.index:
                self._error(
                    "REQUEST.STAGE_BINDING",
                    stage_path,
                    "Load_Config/Start_Comp explanations do not bind graph order",
                )
                continue

            source_path = source_configs.get(op_id)
            if source_path is None:
                self._error("REQUEST.SOURCE_MISSING", stage_path, f"missing source config for {op_id}")
                continue
            config = self._load_object(source_path.resolve(), "REQUEST.SOURCE_PARSE", f"{stage_path}.source")
            if not isinstance(config, Mapping):
                continue
            mask = config.get("CONFIG")
            if not isinstance(mask, str) or len(mask) != 8 or set(mask) - {"0", "1"}:
                self._error("REQUEST.CONFIG_MASK", f"{stage_path}.CONFIG", "requires an eight-bit mask")
                continue
            iga_enable, lsu_enable = mask[0] == "1", mask[1] == "1"
            iga_update, lsu_update = mask[4] == "1", mask[5] == "1"
            enabled_slices = [
                item for item in range(self.profile.slices)
                if (operator["used_slices"] >> item) & 1
            ]

            loaded_states = self._load_stream_states(root, op_id, config, stage_path)
            for slice_id in enabled_slices:
                if not lsu_enable:
                    runtime[slice_id] = {}
                elif lsu_update:
                    runtime[slice_id] = {
                        name: _StreamState(
                            item.resource,
                            item.mode,
                            item.bits,
                            item.initial_bits,
                            item.metadata,
                            item.source_config,
                        )
                        for name, item in loaded_states.items()
                    }
                elif not runtime[slice_id]:
                    self._error(
                        "REQUEST.LSU_REUSE_WITHOUT_STATE",
                        f"{stage_path}.slice[{slice_id}]",
                        "LSU reuse has no prior runtime stream state",
                    )

                if not iga_enable:
                    iga_config[slice_id] = None
                elif iga_update:
                    iga_config[slice_id] = config
                elif iga_config[slice_id] is None:
                    self._error(
                        "REQUEST.IGA_REUSE_WITHOUT_STATE",
                        f"{stage_path}.slice[{slice_id}]",
                        "IGA reuse has no prior index-generator state",
                    )

            stage_writes = [
                item for item in instructions
                if item.kind == "Write_Reg" and load.index < item.index < start.index
            ]
            for instruction in stage_writes:
                if instruction.slice_id not in enabled_slices:
                    self._error(
                        "REQUEST.WRITE_SLICE",
                        f"$.execplan[{instruction.index}]",
                        "Write_Reg targets a slice outside this stage mask",
                    )
                    continue
                assert instruction.register is not None
                first = (instruction.register >> 12) & 0x3
                if first == 0:
                    self._error(
                        "REQUEST.IGA_WREG_UNMODELED",
                        f"$.execplan[{instruction.index}]",
                        "index-generator Write_Reg prevents exact address enumeration",
                    )
                    continue
                target = _stream_write_target(instruction.register)
                if target is None:
                    continue
                state = runtime[instruction.slice_id].get(target)
                if state is None:
                    self._error(
                        "REQUEST.WRITE_TARGET",
                        f"$.execplan[{instruction.index}]",
                        f"Write_Reg targets inactive {target}",
                    )
                    continue
                changed = self._apply_stream_write(state, instruction, stage_path)
                if any(name != "base_addr" for name in changed):
                    self._error(
                        "REQUEST.STREAM_WREG_UNMODELED",
                        f"$.execplan[{instruction.index}]",
                        f"Write_Reg changes non-base stream fields {sorted(changed)}",
                    )

            regions = self._regions_for_operator(operator, params, sca_entries, stage_path)
            streams_facts: list[dict[str, Any]] = []
            if lsu_enable:
                for slice_id in enabled_slices:
                    index_config = iga_config[slice_id]
                    if not isinstance(index_config, Mapping):
                        continue
                    for resource, state in sorted(runtime[slice_id].items()):
                        target = RESOURCE_TARGET[resource]
                        tensor = self._operator_tensor(operator, target)
                        if tensor is None:
                            self._error(
                                "REQUEST.GRAPH_TARGET",
                                f"{stage_path}.{resource}",
                                f"active stream target {target} is absent from graph operator",
                            )
                            continue
                        fact, count, addresses = self._enumerate_stream(
                            stage_path=stage_path,
                            op_id=op_id,
                            execution_slice=slice_id,
                            state=state,
                            index_config=index_config,
                            tensor=tensor,
                            allowed_regions=regions.get(target, []),
                        )
                        streams_facts.append(fact)
                        request_total += count
                        unique_global.update(addresses)

            stage_facts.append(
                {
                    "stage_index": stage_index,
                    "op_id": op_id,
                    "op_type": operator["type"],
                    "load_instruction_index": load.index,
                    "start_instruction_index": start.index,
                    "write_reg_count": len(stage_writes),
                    "enabled_slices": enabled_slices,
                    "CONFIG": {
                        "IGA": {"enable": iga_enable, "update": iga_update},
                        "LSU": {"enable": lsu_enable, "update": lsu_update},
                    },
                    "streams": streams_facts,
                }
            )

        facts = {
            "target_profile": asdict(self.profile),
            "rtl_equation": "(permute26((sum(idx[i]*stride[i])+transfer_bias)>>4)+(base_addr>>4)) mod 2^26",
            "index_enumeration": "exact expression evaluation over the Cartesian product of referenced hardware loop counters",
            "padding_tailing_request_policy": "requests are enumerated before RD/WR data-channel masking; padding/tailing do not suppress Memory_AG requests",
            "graph": str(graph_path),
            "graph_sha256": _sha256_file(graph_path) if graph_path.is_file() else None,
            "operator_count": len(operators),
            "request_count_with_multiplicity": request_total,
            "unique_request_address_count": len(unique_global),
            "unique_request_addresses_sha256": _sha256_addresses(unique_global),
            "stages": stage_facts,
            "issue_count": len(self._issues),
        }
        return RequestAddressValidationReport(
            graph_root=str(root),
            valid=not self._issues,
            issues=list(self._issues),
            facts=facts,
        )

    def _operators(self, graph: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not isinstance(graph, Mapping):
            self._error("REQUEST.GRAPH_SCHEMA", "$.graph", "graph must be an object")
            return [], {}
        raw_params = graph.get("params", {})
        params = {
            str(key): value
            for key, value in raw_params.items()
            if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
        } if isinstance(raw_params, Mapping) else {}
        raw = graph.get("operators")
        if not isinstance(raw, list):
            self._error("REQUEST.GRAPH_SCHEMA", "$.graph.operators", "operators must be an array")
            return [], params
        result: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            path = f"$.graph.operators[{index}]"
            if not isinstance(item, Mapping):
                self._error("REQUEST.GRAPH_SCHEMA", path, "operator must be an object")
                continue
            try:
                used_slices = _parse_int(item.get("used_slices"))
            except ValueError as error:
                self._error("REQUEST.GRAPH_SCHEMA", f"{path}.used_slices", str(error))
                continue
            op_id, op_type = item.get("id"), item.get("type")
            if not isinstance(op_id, str) or not isinstance(op_type, str):
                self._error("REQUEST.GRAPH_SCHEMA", path, "id and type must be strings")
                continue
            result.append(
                {
                    "id": op_id,
                    "type": op_type,
                    "used_slices": used_slices,
                    "inputs": item.get("inputs", {}),
                    "output": item.get("output", item.get("D")),
                }
            )
        return result, params

    def _sca_entries(self, root: Path) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for name in ("sca_cfg.json", "sca_cfg_D.json"):
            payload = self._load_object(root / name, "REQUEST.SCA_PARSE", f"$.{name}")
            if not isinstance(payload, Mapping):
                continue
            for key, value in payload.items():
                if isinstance(value, Mapping):
                    if key in result:
                        self._error("REQUEST.SCA_DUPLICATE", f"$.sca.{key}", "duplicate SCA key")
                    result[str(key)] = value
        return result

    def _instructions(self, root: Path) -> list[_Instruction]:
        execplan = root / "install" / "execplan.txt"
        explanation_path = root / "instructions_explained.txt"
        try:
            lines = [line.strip() for line in execplan.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, UnicodeError) as error:
            self._error("REQUEST.EXECPLAN_READ", str(execplan), str(error))
            return []
        words: list[int] = []
        for index, line in enumerate(lines):
            if len(line) != 128 or set(line) - {"0", "1"}:
                self._error("REQUEST.EXECPLAN_FORMAT", f"{execplan}:{index + 1}", "requires 128 binary digits")
                continue
            words.extend((int(line[64:], 2), int(line[:64], 2)))
        if words and words[-1] == 0:
            words.pop()
        try:
            explained_lines = explanation_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self._error("REQUEST.EXPLANATION_READ", str(explanation_path), str(error))
            return []
        explanations: dict[int, str] = {}
        for line in explained_lines:
            match = COMMAND_RE.match(line)
            if match is None:
                continue
            index, explained_word = int(match.group(1)), int(match.group(2), 2)
            if index >= len(words) or words[index] != explained_word:
                self._error("REQUEST.EXPLANATION_BITS", f"{explanation_path}:{index}", "word differs from execplan")
                continue
            if index in explanations:
                self._error(
                    "REQUEST.EXPLANATION_DUPLICATE",
                    f"{explanation_path}:{index}",
                    "instruction index is explained more than once",
                )
                continue
            explanations[index] = match.group(3)
        if set(explanations) != set(range(len(words))):
            self._error("REQUEST.EXPLANATION_COVERAGE", str(explanation_path), "must cover every real instruction")

        result: list[_Instruction] = []
        for index, word in enumerate(words):
            explanation = explanations.get(index, "")
            opcode = word & 0x7
            operator_match = LOAD_RE.match(explanation) or START_RE.match(explanation)
            operator = operator_match.group(1) if operator_match else None
            if opcode == 0:
                result.append(_Instruction(index, word, "Load_Config", explanation, operator, bool((word >> 31) & 1)))
            elif opcode == 1:
                result.append(_Instruction(index, word, "Clock_Enable", explanation, operator))
            elif opcode == 4:
                reserved = (word >> 8) & 0x3FF
                slice_id = (word >> 3) & 0x1F
                register = (word >> 18) & 0x3FFF
                value = (word >> 32) & 0xFFFFFFFF
                if reserved:
                    self._error("REQUEST.WRITE_RESERVED", f"$.execplan[{index}]", "reserved Write_Reg bits must be zero")
                self._validate_write_explanation(index, explanation, slice_id, register, value)
                result.append(_Instruction(index, word, "Write_Reg", explanation, None, None, slice_id, register, value))
            elif opcode == 5:
                result.append(_Instruction(index, word, "Start_Comp", explanation, operator))
            else:
                self._error("REQUEST.OPCODE", f"$.execplan[{index}]", f"unsupported opcode {opcode}")
        return result

    def _validate_write_explanation(
        self, index: int, explanation: str, slice_id: int, register: int, value: int
    ) -> None:
        expected = {"slice": slice_id, "register": register, "value": value}
        bases = {"slice": 2, "register": 2, "value": 16}
        for name, pattern in EXPLAINED_INT_RE.items():
            match = pattern.search(explanation)
            if match is None or int(match.group(1), bases[name]) != expected[name]:
                self._error(
                    "REQUEST.WRITE_EXPLANATION",
                    f"$.execplan[{index}]",
                    f"{name} explanation differs from machine bits",
                )

    def _load_stream_states(
        self,
        root: Path,
        op_id: str,
        config: Mapping[str, Any],
        stage_path: str,
    ) -> dict[str, _StreamState]:
        artifact_dir = root / "config" / op_id
        images = self._parsed_stream_images(artifact_dir / "parsed_bitstream.txt")
        review = self._load_object(artifact_dir / "mapping_review.json", "REQUEST.MAPPING_PARSE", f"{stage_path}.mapping")
        mapping: dict[str, str] = {}
        if isinstance(review, Mapping) and isinstance(review.get("node_to_resource"), list):
            for row in review["node_to_resource"]:
                if isinstance(row, Mapping) and isinstance(row.get("node"), str) and isinstance(row.get("resource"), str):
                    mapping[row["node"]] = row["resource"]
        streams = config.get("stream_engine")
        if not isinstance(streams, Mapping):
            self._error("REQUEST.STREAM_SCHEMA", f"{stage_path}.stream_engine", "must be an object")
            return {}
        result: dict[str, _StreamState] = {}
        for name, metadata in streams.items():
            if not isinstance(metadata, Mapping):
                continue
            resource = mapping.get(f"STREAM.{name}")
            if resource not in RESOURCE_TARGET:
                self._error("REQUEST.STREAM_MAPPING", f"{stage_path}.stream_engine.{name}", "missing physical stream mapping")
                continue
            expected_target = RESOURCE_TARGET[resource]
            if metadata.get("target") != expected_target:
                self._error(
                    "REQUEST.TARGET_RESOURCE",
                    f"{stage_path}.stream_engine.{name}.target",
                    f"{resource} is fixed to {expected_target}, got {metadata.get('target')!r}",
                )
            bits = images.get(resource)
            if bits is None:
                self._error("REQUEST.STREAM_IMAGE", f"{stage_path}.{resource}", "parsed bitstream lacks mapped stream image")
                continue
            mode = "write" if resource.startswith("WRITE") else "read"
            result[resource] = _StreamState(resource, mode, bits, bits, metadata, config)
        return result

    def _parsed_stream_images(self, path: Path) -> dict[str, str]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self._error("REQUEST.PARSED_READ", str(path), str(error))
            return {}
        sections: dict[str, list[str]] = {}
        current: str | None = None
        for raw in lines:
            line = raw.strip()
            if line.endswith(":"):
                current = line[:-1]
                sections[current] = []
            elif line and current is not None:
                sections[current].append(line)
        result: dict[str, str] = {}
        for mode, layout in STREAM_LAYOUT.items():
            payloads = sections.get(str(layout["section"]), [])
            expected = int(layout["slots"]) * int(layout["chunks"])
            if not payloads:
                continue
            if len(payloads) != expected:
                self._error("REQUEST.PARSED_STREAM_COUNT", str(path), f"{layout['section']} expected {expected} chunks")
                continue
            width = int(layout["port_width"])
            chunks = int(layout["chunks"])
            for slot in range(int(layout["slots"])):
                bits = ""
                for chunk in payloads[slot * chunks : (slot + 1) * chunks]:
                    if chunk == "0":
                        bits += "0" * width
                    elif chunk.startswith("1 ") and len(chunk[2:]) == width and not (set(chunk[2:]) - {"0", "1"}):
                        bits += chunk[2:]
                    else:
                        self._error("REQUEST.PARSED_STREAM_FORMAT", str(path), f"invalid {layout['section']} chunk")
                resource = f"{'READ_STREAM' if mode == 'read' else 'WRITE_STREAM'}{slot}"
                result[resource] = bits
        return result

    def _apply_stream_write(
        self, state: _StreamState, instruction: _Instruction, stage_path: str
    ) -> set[str]:
        assert instruction.register is not None and instruction.value is not None
        layout = STREAM_LAYOUT[state.mode]
        local = instruction.register & 0x1F
        register_index, high_half = local >> 1, local & 1
        chunks, width = int(layout["chunks"]), int(layout["port_width"])
        half_width = width // 2
        if register_index >= chunks:
            self._error("REQUEST.WRITE_REGISTER_RANGE", stage_path, f"local register {local} exceeds {state.resource}")
            return set()
        if instruction.value >> half_width:
            self._error(
                "REQUEST.WRITE_DATA_WIDTH",
                f"$.execplan[{instruction.index}]",
                f"upper Write_Reg data bits are discarded by {width}-bit stream config port",
            )
        chunk = chunks - 1 - register_index
        start = chunk * width + (0 if high_half else half_width)
        end = start + half_width
        replacement = format(instruction.value & ((1 << half_width) - 1), f"0{half_width}b")
        before = state.bits
        state.bits = before[:start] + replacement + before[end:]
        changed: set[str] = set()
        for name, left, right in _field_ranges(state.mode):
            if max(left, start) < min(right, end) and before[left:right] != state.bits[left:right]:
                changed.add(name)
        return changed

    def _regions_for_operator(
        self,
        operator: Mapping[str, Any],
        params: Mapping[str, int],
        sca: Mapping[str, Mapping[str, Any]],
        stage_path: str,
    ) -> dict[str, list[RequestRegion]]:
        result: dict[str, list[RequestRegion]] = {}
        for target in RESOURCE_TARGET.values():
            tensor = self._operator_tensor(operator, target)
            if not isinstance(tensor, Mapping):
                continue
            try:
                shape = _shape(tensor.get("shape"), params)
                dtype = str(tensor.get("dtype", "fp32")).lower()
                interleave = _positive_int(tensor.get("bank_interleave", 1))
                per_bank = math.prod(shape) * DTYPE_BYTES[dtype] // interleave
                length = _align_up(per_bank, 16)
            except (KeyError, TypeError, ValueError) as error:
                self._error("REQUEST.TENSOR_SCHEMA", f"{stage_path}.{target}", str(error))
                continue
            manifest_target = "Bp" if target == "B'" else target
            if (
                target == "B'"
                and str(operator.get("type", "")).startswith(
                    "resnet50_conv_node0004_wave"
                )
            ):
                # node0004 stream2 is an offset view into the same complete
                # activation allocation carried by stream1, not a second SCA
                # matrix.  The specialized control handler binds its +7168B
                # starting address; request coverage remains bounded by B.
                manifest_target = "B"
            prefix = f"{operator['id']}_matrix{manifest_target}_slice"
            regions: list[RequestRegion] = []
            for key, entry in sca.items():
                if not key.startswith(prefix):
                    continue
                try:
                    address = _parse_int(entry.get("base_addr"))
                except ValueError as error:
                    self._error("REQUEST.SCA_ADDRESS", f"$.sca.{key}", str(error))
                    continue
                slice_id, bank, offset = _decode_byte_address(address, self.profile)
                regions.append(RequestRegion(key, target, slice_id, bank, offset, offset + length))
            if not regions:
                self._error("REQUEST.SCA_REGION", f"{stage_path}.{target}", "no SCA tensor regions")
            result[target] = regions
        return result

    @staticmethod
    def _operator_tensor(operator: Mapping[str, Any], target: str) -> Mapping[str, Any] | None:
        if target == "D":
            value = operator.get("output")
        else:
            inputs = operator.get("inputs")
            value = inputs.get(target) if isinstance(inputs, Mapping) else None
        return value if isinstance(value, Mapping) else None

    def _enumerate_stream(
        self,
        *,
        stage_path: str,
        op_id: str,
        execution_slice: int,
        state: _StreamState,
        index_config: Mapping[str, Any],
        tensor: Mapping[str, Any],
        allowed_regions: Sequence[RequestRegion],
    ) -> tuple[dict[str, Any], int, set[int]]:
        fields = _decode_stream_fields(state.bits, state.mode)
        total_size = fields["total_size"]
        strides = fields["dim_stride"]
        remapping = fields["address_remapping"]
        base_addr = fields["base_addr"]
        path = f"{stage_path}.slice[{execution_slice}].{state.resource}"
        if total_size <= 0:
            self._error("REQUEST.TRANSACTION_SIZE", path, "encoded transaction size must be nonzero")
            return {}, 0, set()
        if sorted(remapping) != list(range(26)):
            self._error("REQUEST.REMAP", path, "encoded remapping is not a permutation of 0..25")
            return {}, 0, set()
        try:
            tuples = _index_tuples(
                state.metadata,
                index_config,
                maximum=self.max_index_assignments,
            )
        except _IndexModelError as error:
            self._error("REQUEST.INDEX_MODEL", path, str(error))
            return {}, 0, set()

        storage_contract: dict[str, Any] | None = None
        # The guarded ABI governs read-side padding and payload addressing.
        # Write layouts remain bound by the semantic/package contract and do
        # not use RD_Data_Channel padding fields.
        raw_storage_contract = tensor.get("logical_storage") if state.mode == "read" else None
        if raw_storage_contract is not None:
            try:
                schema = (
                    raw_storage_contract.get("schema")
                    if isinstance(raw_storage_contract, Mapping)
                    else None
                )
                if schema == "maxpool-guarded-c4hwc4-storage-v1":
                    storage_contract = _maxpool_guarded_storage_contract(
                        tensor,
                        fields,
                        raw_storage_contract,
                    )
                elif schema == "resnet50-gap-c8hw8-input-v1":
                    storage_contract = _gap_c8hw8_storage_contract(
                        tensor,
                        fields,
                        raw_storage_contract,
                    )
                else:
                    raise ValueError("unsupported logical_storage schema")
            except (TypeError, ValueError) as error:
                self._error("REQUEST.LOGICAL_STORAGE_SCHEMA", path, str(error))

        addresses: dict[int, dict[str, int]] = {}
        logical_storage_proof: dict[str, Any] | None = (
            {
                "schema": storage_contract["schema"],
                "checked_valid_byte_count_with_multiplicity": 0,
                "padding_masked_byte_count_with_multiplicity": 0,
                "logical_payload_byte_count_with_multiplicity": 0,
                "logical_address_mismatch_count": 0,
                "padding_mask_mismatch_count": 0,
                "first_mismatch": None,
            }
            if storage_contract is not None
            else None
        )
        transaction_wrap = False
        address_wrap = False
        for indexes in tuples:
            bias = sum((indexes[index] & 0xFFFF) * strides[index] for index in range(3))
            if bias >= (1 << 30):
                transaction_wrap = True
            bias &= (1 << 30) - 1
            remaining = total_size
            transfer_bias = 0
            while remaining > 0:
                transfer_addr = (bias + transfer_bias) & ((1 << 30) - 1)
                if bias + transfer_bias >= (1 << 30):
                    transaction_wrap = True
                position = transfer_addr & 0xF
                size = min(remaining, 16 - position)
                unmapped = transfer_addr >> 4
                mapped = remap_word_address(unmapped, remapping)
                summed = mapped + (base_addr >> 4)
                if summed >= (1 << 26):
                    address_wrap = True
                word_address = summed & ((1 << 26) - 1)
                stats = addresses.setdefault(
                    word_address,
                    {
                        "multiplicity": 0,
                        "valid_byte_count_with_multiplicity": 0,
                        "padding_masked_byte_count_with_multiplicity": 0,
                        "logical_payload_byte_count_with_multiplicity": 0,
                    },
                )
                stats["multiplicity"] += 1
                stats["valid_byte_count_with_multiplicity"] += size
                for lane_offset in range(size):
                    transfer_lane_bias = transfer_bias + lane_offset
                    lane_indexes = _transfer_lane_indexes(
                        indexes,
                        transfer_lane_bias,
                        fields,
                    )
                    padded = _padding_masked(lane_indexes, fields)
                    if padded:
                        stats["padding_masked_byte_count_with_multiplicity"] += 1
                    else:
                        stats["logical_payload_byte_count_with_multiplicity"] += 1
                    if logical_storage_proof is not None and storage_contract is not None:
                        logical_storage_proof[
                            "checked_valid_byte_count_with_multiplicity"
                        ] += 1
                        if padded:
                            logical_storage_proof[
                                "padding_masked_byte_count_with_multiplicity"
                            ] += 1
                        else:
                            logical_storage_proof[
                                "logical_payload_byte_count_with_multiplicity"
                            ] += 1
                        lane_position = position + lane_offset
                        actual_byte_address = (word_address << 4) + lane_position
                        if (
                            storage_contract["schema"]
                            == "maxpool-guarded-c4hwc4-storage-v1"
                        ):
                            mismatch = _maxpool_guarded_lane_mismatch(
                                contract=storage_contract,
                                transaction_indexes=indexes,
                                lane_indexes=lane_indexes,
                                transfer_lane_bias=transfer_lane_bias,
                                padded=padded,
                                actual_byte_address=actual_byte_address,
                                allowed_regions=allowed_regions,
                                profile=self.profile,
                            )
                        else:
                            mismatch = _gap_c8hw8_lane_mismatch(
                                contract=storage_contract,
                                transaction_indexes=indexes,
                                lane_indexes=lane_indexes,
                                transfer_lane_bias=transfer_lane_bias,
                                padded=padded,
                                actual_byte_address=actual_byte_address,
                                allowed_regions=allowed_regions,
                                profile=self.profile,
                            )
                        if mismatch is not None:
                            mismatch_kind, message = mismatch
                            logical_storage_proof[mismatch_kind] += 1
                            if logical_storage_proof["first_mismatch"] is None:
                                logical_storage_proof["first_mismatch"] = message
                remaining -= size
                transfer_bias += size
        if transaction_wrap:
            self._error("REQUEST.TRANSACTION_WRAP", path, "30-bit transaction address wraps")
        if address_wrap:
            self._error("REQUEST.BASE_ADD_WRAP", path, "26-bit post-remap base addition wraps")

        address_rows: list[dict[str, Any]] = []
        first_request: dict[str, Any] | None = None
        last_request: dict[str, Any] | None = None
        for word_address, stats in sorted(addresses.items()):
            byte_address = word_address << 4
            slice_id, bank, offset = _decode_byte_address(byte_address, self.profile)
            row = (byte_address >> 10) & 0x1FFF
            column = (byte_address >> 4) & 0x3F
            if slice_id >= self.profile.slices or bank >= self.profile.banks_per_slice:
                self._error("REQUEST.ADDRESS_PROFILE", path, f"request 0x{byte_address:08X} exceeds slice/bank profile")
            if row >= self.profile.ddr_rows:
                self._error("REQUEST.ROW_LIMIT", path, f"request row {row} must be < {self.profile.ddr_rows}")
            hits = [
                region.key for region in allowed_regions
                if region.slice_id == slice_id
                and region.bank == bank
                and region.start <= offset
                and offset + 16 <= region.end
            ]
            if not hits:
                self._error(
                    "REQUEST.OUTSIDE_TENSOR_REGION",
                    path,
                    f"request 0x{byte_address:08X} does not fit a declared {RESOURCE_TARGET[state.resource]} region",
                )
            request = {
                "word_addr_26b": f"0x{word_address:07X}",
                "byte_addr_30b": f"0x{byte_address:08X}",
                "slice": slice_id,
                "bank": bank,
                "row": row,
                "column": column,
                **stats,
                "region_hits": hits,
            }
            if first_request is None:
                first_request = request
            last_request = request
            if self.include_request_rows:
                address_rows.append(request)
        initial_fields = _decode_stream_fields(state.initial_bits, state.mode)
        non_base_drift = [
            name for name in fields
            if name != "base_addr" and fields[name] != initial_fields[name]
        ]
        if non_base_drift:
            self._error("REQUEST.STREAM_STATE_DRIFT", path, f"unmodeled fields changed: {non_base_drift}")
        if logical_storage_proof is not None:
            if logical_storage_proof["logical_address_mismatch_count"]:
                self._error(
                    "REQUEST.LOGICAL_STORAGE_ADDRESS",
                    path,
                    str(logical_storage_proof["first_mismatch"]),
                )
            elif logical_storage_proof["padding_mask_mismatch_count"]:
                self._error(
                    "REQUEST.LOGICAL_STORAGE_PADDING",
                    path,
                    str(logical_storage_proof["first_mismatch"]),
                )
            logical_storage_proof["valid"] = not (
                logical_storage_proof["logical_address_mismatch_count"]
                or logical_storage_proof["padding_mask_mismatch_count"]
            )
        fact = {
            "execution_slice": execution_slice,
            "resource": state.resource,
            "target": RESOURCE_TARGET[state.resource],
            "mode": state.mode,
            "base_addr": f"0x{base_addr:08X}",
            "idx_size_encoded": fields["idx_size"],
            "transaction_size_bytes": total_size,
            "dim_stride_bytes": strides,
            "address_remapping": remapping,
            "index_tuple_count": len(tuples),
            "request_count_with_multiplicity": sum(
                item["multiplicity"] for item in addresses.values()
            ),
            "unique_request_count": len(addresses),
            "unique_request_addresses_sha256": _sha256_addresses(set(addresses)),
            "valid_byte_count_with_multiplicity": sum(
                item["valid_byte_count_with_multiplicity"] for item in addresses.values()
            ),
            "padding_masked_byte_count_with_multiplicity": sum(
                item["padding_masked_byte_count_with_multiplicity"]
                for item in addresses.values()
            ),
            "logical_payload_byte_count_with_multiplicity": sum(
                item["logical_payload_byte_count_with_multiplicity"]
                for item in addresses.values()
            ),
            "logical_storage_proof": logical_storage_proof,
            "request_rows_included": self.include_request_rows,
            "first_request": first_request,
            "last_request": last_request,
        }
        if self.include_request_rows:
            fact["requests"] = address_rows
        return (
            fact,
            sum(item["multiplicity"] for item in addresses.values()),
            set(addresses),
        )

    def _load_object(self, path: Path, code: str, issue_path: str) -> Any:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._error(code, issue_path, str(error))
            return None
        if not isinstance(value, Mapping):
            self._error(code, issue_path, "JSON root must be an object")
            return None
        return value

    def _error(self, code: str, path: str, message: str) -> None:
        self._issues.append(ValidationIssue(code, path, message))


def remap_word_address(value: int, remapping: Sequence[int]) -> int:
    """Mirror ``request_addr_mapped[i] = transfer_addr_nooff[map[i]]``."""

    if not 0 <= value < (1 << 26):
        raise ValueError("unmapped word address must fit 26 bits")
    if len(remapping) != 26 or sorted(remapping) != list(range(26)):
        raise ValueError("remapping must be a permutation of 0..25")
    result = 0
    for output_bit, input_bit in enumerate(remapping):
        result |= ((value >> input_bit) & 1) << output_bit
    return result


def enumerate_transfer_word_addresses(
    *,
    indexes: Sequence[int],
    strides: Sequence[int],
    transaction_size: int,
    base_addr: int,
    remapping: Sequence[int],
) -> list[int]:
    """Small public RTL equation model used by focused fault-injection tests."""

    if len(indexes) != 3 or len(strides) != 3:
        raise ValueError("indexes and strides require three entries")
    if not 1 <= transaction_size <= 255:
        raise ValueError("transaction_size must be in 1..255")
    bias = sum((int(indexes[i]) & 0xFFFF) * int(strides[i]) for i in range(3)) & ((1 << 30) - 1)
    result: list[int] = []
    remaining = transaction_size
    transfer_bias = 0
    while remaining:
        transfer_addr = (bias + transfer_bias) & ((1 << 30) - 1)
        size = min(remaining, 16 - (transfer_addr & 0xF))
        mapped = remap_word_address(transfer_addr >> 4, remapping)
        result.append((mapped + (base_addr >> 4)) & ((1 << 26) - 1))
        remaining -= size
        transfer_bias += size
    return result


def _stream_write_target(register: int) -> str | None:
    first = (register >> 12) & 0x3
    second = (register >> 10) & 0x3
    slot = (register >> 5) & 0x1F
    if first != 1:
        return None
    if second == 0 and slot < 4:
        return f"READ_STREAM{slot}"
    if second == 1 and slot == 0:
        return "WRITE_STREAM0"
    return None


def _field_ranges(mode: str) -> list[tuple[str, int, int]]:
    cursor = 0
    result: list[tuple[str, int, int]] = []
    for name, width in READ_FIELD_WIDTHS if mode == "read" else WRITE_FIELD_WIDTHS:
        result.append((name, cursor, cursor + width))
        cursor += width
    expected = 580 if mode == "read" else 496
    if cursor != expected:
        raise AssertionError(f"{mode} field layout is {cursor}, expected {expected}")
    return result


def _decode_stream_fields(bits: str, mode: str) -> dict[str, Any]:
    ranges = {name: (start, end) for name, start, end in _field_ranges(mode)}

    def integer(name: str) -> int:
        start, end = ranges[name]
        return int(bits[start:end], 2)

    def groups(name: str, count: int, width: int) -> list[int]:
        start, end = ranges[name]
        payload = bits[start:end]
        return [int(payload[index * width : (index + 1) * width], 2) for index in range(count)]

    encoded_remap = groups("address_remapping", 26, 5)
    result = {
        "base_addr": integer("base_addr"),
        "idx_size": groups("idx_size", 3, 8),
        "idx_size_log": groups("idx_size_log", 3, 3),
        "total_size": integer("total_size"),
        "dim_stride": groups("dim_stride", 3, 20),
        "address_remapping": list(reversed(encoded_remap)),
        # The encoder deliberately reverses this JSON list before packing it.
        # Reversing the packed groups here therefore exposes the lane-indexed
        # values seen by WR_Buffer_AG, rather than their serial bit order.
        "buf_spatial_stride": list(
            reversed(groups("buf_spatial_stride", 16, 5))
        ),
        "buf_spatial_size": integer("buf_spatial_size"),
    }
    if mode == "read":
        padding_ranges = groups("idx_padding_range", 6, 12)
        result.update(
            {
                "padding_reg_value": integer("padding_reg_value"),
                "padding_enable": groups("padding_enable", 3, 1),
                "padding_low_bound": padding_ranges[:3],
                "padding_up_bound": padding_ranges[3:],
            }
        )
    else:
        result.update(
            {
                "padding_reg_value": 0,
                "padding_enable": [0, 0, 0],
                "padding_low_bound": [0, 0, 0],
                "padding_up_bound": [0, 0, 0],
            }
        )
    return result


def _transfer_lane_indexes(
    transaction_indexes: Sequence[int],
    transfer_lane_bias: int,
    fields: Mapping[str, Any],
) -> tuple[int, int, int]:
    """Mirror the RD_Data_Channel byte-lane TSA index equations."""

    # JSON list fields are serialized most-significant element first, while
    # the RTL ports are packed arrays whose element 0 occupies the least
    # significant field.  Transaction address enumeration can stay in JSON
    # order because indexes and dim_stride reverse together in hardware.
    # RD_Data_Channel's per-byte equations, however, index the packed arrays
    # directly, so model that reversal explicitly and convert back afterwards.
    rtl_indexes = list(reversed(transaction_indexes))
    rtl_sizes = list(reversed(fields["idx_size"]))
    rtl_logs = list(reversed(fields["idx_size_log"]))
    rtl_transfer_indexes = (
        (transfer_lane_bias >> rtl_logs[1]) & rtl_sizes[0],
        (transfer_lane_bias >> rtl_logs[2]) & rtl_sizes[1],
        transfer_lane_bias & rtl_sizes[2],
    )
    rtl_lane_indexes = tuple(
        ((int(rtl_indexes[index]) & 0xFFFF) + rtl_transfer_indexes[index])
        & 0xFFFF
        for index in range(3)
    )
    return tuple(reversed(rtl_lane_indexes))  # type: ignore[return-value]


def _padding_masked(indexes: Sequence[int], fields: Mapping[str, Any]) -> bool:
    return any(
        bool(fields["padding_enable"][index])
        and (
            indexes[index] < fields["padding_low_bound"][index]
            or indexes[index] > fields["padding_up_bound"][index]
        )
        for index in range(3)
    )


def _maxpool_guarded_storage_contract(
    tensor: Mapping[str, Any],
    fields: Mapping[str, Any],
    raw: Any,
) -> dict[str, Any]:
    """Validate the one explicit physical storage ABI used by node-0002.

    This is deliberately schema-specific.  Merely adding an allocation size to
    an arbitrary graph must never weaken request validation.
    """

    if not isinstance(raw, Mapping):
        raise TypeError("logical_storage must be an object")
    if raw.get("schema") != "maxpool-guarded-c4hwc4-storage-v1":
        raise ValueError("unsupported logical_storage schema")
    logical_shape = raw.get("logical_shape_nhwc")
    origin = raw.get("coordinate_origin_xy")
    if (
        not isinstance(logical_shape, list)
        or len(logical_shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in logical_shape)
    ):
        raise ValueError("logical_shape_nhwc must contain three positive integers")
    if origin != [1, 1]:
        raise ValueError("node-0002 guarded storage requires coordinate_origin_xy=[1,1]")
    height, width, channels = logical_shape
    channel_block = raw.get("channel_block")
    if channel_block != 4 or channels % channel_block:
        raise ValueError("C4HWC4 storage requires channels divisible by four")
    if raw.get("layout") != "C4HWC4" or raw.get("padding_value") != 0:
        raise ValueError("guarded storage requires C4HWC4 layout and zero padding")
    payload_offset = origin[1] * width * channel_block + origin[0] * channel_block
    payload_bytes = height * width * channels
    allocation_bytes = _align_up(payload_offset + payload_bytes, 16)
    expected = {
        "payload_offset_bytes": payload_offset,
        "payload_bytes": payload_bytes,
        "allocation_bytes": allocation_bytes,
        "prefix_guard_bytes": payload_offset,
        "suffix_guard_bytes": allocation_bytes - payload_offset - payload_bytes,
    }
    for name, value in expected.items():
        if raw.get(name) != value:
            raise ValueError(f"logical_storage {name} must be {value}")
    physical_shape = tensor.get("shape")
    if physical_shape != [1, 1, allocation_bytes] or tensor.get("dtype") != "uint8":
        raise ValueError("graph tensor shape/dtype does not equal guarded byte allocation")
    if (
        fields["idx_size"] != [0, 0, 3]
        or fields["idx_size_log"] != [0, 0, 0]
        or fields["total_size"] != 4
        or fields["dim_stride"] != [4, width * 4, height * width * 4]
        or fields["padding_enable"] != [1, 1, 0]
        or fields["padding_low_bound"][:2] != origin
        or fields["padding_up_bound"][:2] != [origin[0] + width - 1, origin[1] + height - 1]
        or fields["padding_reg_value"] != raw["padding_value"]
        or fields["address_remapping"] != list(range(26))
    ):
        raise ValueError("encoded read stream differs from guarded C4HWC4 storage ABI")
    return dict(raw)


def _maxpool_guarded_lane_mismatch(
    *,
    contract: Mapping[str, Any],
    transaction_indexes: Sequence[int],
    lane_indexes: Sequence[int],
    transfer_lane_bias: int,
    padded: bool,
    actual_byte_address: int,
    allowed_regions: Sequence[RequestRegion],
    profile: TargetProfile,
) -> tuple[str, str] | None:
    height, width, channels = contract["logical_shape_nhwc"]
    origin_x, origin_y = contract["coordinate_origin_xy"]
    expected_padding = not (
        origin_x <= lane_indexes[0] < origin_x + width
        and origin_y <= lane_indexes[1] < origin_y + height
    )
    if padded != expected_padding:
        return (
            "padding_mask_mismatch_count",
            f"lane indexes {tuple(lane_indexes)} padding={padded}, expected={expected_padding}",
        )
    if padded:
        return None

    slice_id, bank, offset = _decode_byte_address(actual_byte_address, profile)
    regions = [
        item
        for item in allowed_regions
        if item.slice_id == slice_id and item.bank == bank
    ]
    if len(regions) != 1:
        return (
            "logical_address_mismatch_count",
            f"logical storage byte maps to {len(regions)} candidate regions",
        )
    region = regions[0]
    x = lane_indexes[0] - origin_x
    y = lane_indexes[1] - origin_y
    channel_block = int(transaction_indexes[2]) & 0xFFFF
    channel_inner = transfer_lane_bias & 0x3
    channel = channel_block * 4 + channel_inner
    if not (0 <= channel < channels):
        return (
            "logical_address_mismatch_count",
            f"derived channel {channel} is outside 0..{channels - 1}",
        )
    expected_offset = (
        contract["payload_offset_bytes"]
        + channel_block * height * width * 4
        + y * width * 4
        + x * 4
        + channel_inner
    )
    actual_offset = offset - region.start
    if actual_offset != expected_offset:
        return (
            "logical_address_mismatch_count",
            f"logical (y={y},x={x},c={channel}) maps to byte {actual_offset}, expected {expected_offset}",
        )
    return None


def _gap_c8hw8_storage_contract(
    tensor: Mapping[str, Any],
    fields: Mapping[str, Any],
    raw: Any,
) -> dict[str, Any]:
    """Validate the exact guarded C8HW8 ABI used by hwop-0071-00."""

    if not isinstance(raw, Mapping):
        raise TypeError("logical_storage must be an object")
    if raw.get("schema") != "resnet50-gap-c8hw8-input-v1":
        raise ValueError("unsupported logical_storage schema")
    if (
        raw.get("logical_shape_nchw") != [2048, 7, 7]
        or raw.get("physical_shape") != [256, 7, 7, 8]
        or raw.get("layout") != "C8HW8"
        or raw.get("payload_bytes") != 100352
        or raw.get("allocation_bytes") != 100416
        or raw.get("prefix_guard_bytes") != 0
        or raw.get("suffix_guard_bytes") != 64
    ):
        raise ValueError("GAP logical_storage geometry/guard differs")
    if tensor.get("shape") != [1, 1, 100416] or tensor.get("dtype") != "uint8":
        raise ValueError("GAP graph tensor does not equal guarded allocation")
    if (
        fields["idx_size"] != [7, 3, 0]
        or fields["idx_size_log"] != [3, 5, 0]
        or fields["total_size"] != 32
        or fields["dim_stride"] != [392, 8, 0]
        or fields["padding_enable"] != [0, 1, 0]
        or fields["padding_low_bound"][1] != 0
        or fields["padding_up_bound"][1] != 48
        or fields["padding_reg_value"] != 0
        or fields["buf_spatial_size"] != 16
        or fields["buf_spatial_stride"]
        != [0, 4, 8, 12, 16, 20, 24, 28, 1, 5, 9, 13, 17, 21, 25, 29]
        or fields["address_remapping"] != list(range(26))
    ):
        raise ValueError("encoded read stream differs from GAP C8HW8 ABI")
    return dict(raw)


def _gap_c8hw8_lane_mismatch(
    *,
    contract: Mapping[str, Any],
    transaction_indexes: Sequence[int],
    lane_indexes: Sequence[int],
    transfer_lane_bias: int,
    padded: bool,
    actual_byte_address: int,
    allowed_regions: Sequence[RequestRegion],
    profile: TargetProfile,
) -> tuple[str, str] | None:
    _ = contract
    spatial = int(lane_indexes[1])
    expected_padding = not 0 <= spatial < 49
    if padded != expected_padding:
        return (
            "padding_mask_mismatch_count",
            f"GAP spatial index {spatial} padding={padded}, expected={expected_padding}",
        )
    if padded:
        return None
    slice_id, bank, offset = _decode_byte_address(actual_byte_address, profile)
    regions = [
        item
        for item in allowed_regions
        if item.slice_id == slice_id and item.bank == bank
    ]
    if len(regions) != 1:
        return (
            "logical_address_mismatch_count",
            f"GAP logical byte maps to {len(regions)} candidate regions",
        )
    channel_block = int(transaction_indexes[0]) & 0xFFFF
    channel_inner = transfer_lane_bias & 0x7
    if not 0 <= channel_block < 256:
        return (
            "logical_address_mismatch_count",
            f"GAP channel block {channel_block} is outside 0..255",
        )
    expected_offset = channel_block * 392 + spatial * 8 + channel_inner
    actual_offset = offset - regions[0].start
    if actual_offset != expected_offset:
        return (
            "logical_address_mismatch_count",
            (
                f"GAP (block={channel_block},spatial={spatial},inner={channel_inner}) "
                f"maps to byte {actual_offset}, expected {expected_offset}"
            ),
        )
    return None


def _index_tuples(
    stream: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    maximum: int,
) -> list[tuple[int, int, int]]:
    modes = stream.get("mem_idx_mode")
    sources = stream.get("idx")
    constants = stream.get("mem_idx_constant")
    if not all(isinstance(item, list) and len(item) == 3 for item in (modes, sources, constants)):
        raise _IndexModelError("stream mem_idx_mode/idx/mem_idx_constant must each have three entries")

    expression_sources: list[str | None] = []
    variable_names: set[str] = set()
    for index, mode in enumerate(modes):
        if mode == "constant" or mode is None:
            expression_sources.append(None)
            continue
        source = sources[index]
        if not isinstance(source, str):
            raise _IndexModelError(f"port {index} requires a named logical index source")
        expression_sources.append(source)
        variable_names.update(_collect_variables(source, config, set()))

    domains = {name: _variable_domain(name, config) for name in sorted(variable_names)}
    assignment_count = math.prod(len(values) for values in domains.values()) if domains else 1
    if assignment_count > maximum:
        raise _IndexModelError(
            f"exact index enumeration needs {assignment_count} assignments, limit is {maximum}"
        )
    result: set[tuple[int, int, int]] = set()
    domain_names = list(domains)
    products = itertools.product(*(domains[name] for name in domain_names)) if domains else [()]
    for values in products:
        environment = dict(zip(domain_names, values, strict=True))
        indexes: list[int] = []
        for index, mode in enumerate(modes):
            if mode == "constant":
                value = int(constants[index]) & 0xFF
                indexes.append(value | 0xFF00 if value & 0x80 else value)
            elif mode is None:
                indexes.append(0)
            else:
                source = expression_sources[index]
                assert source is not None
                indexes.append(_evaluate_source(source, config, environment, set()))
        result.add(tuple(indexes))
    return sorted(result)


def _collect_variables(source: str, config: Mapping[str, Any], visiting: set[str]) -> set[str]:
    if source in visiting:
        raise _IndexModelError(f"cycle in index expression at {source}")
    if source.startswith("DRAM_LC.") or re.fullmatch(r"GROUP[0-4]\.(?:ROW_LC|COL_LC)", source):
        _variable_domain(source, config)
        return {source}
    if source.startswith("LC_PE."):
        visiting = set(visiting)
        visiting.add(source)
        name = source.split(".", 1)[1]
        pes = config.get("lc_pe_configs")
        pe = pes.get(name) if isinstance(pes, Mapping) else None
        if not isinstance(pe, Mapping):
            raise _IndexModelError(f"missing {source}")
        result: set[str] = set()
        for index in range(3):
            port = pe.get(f"inport{index}")
            if not isinstance(port, Mapping) or port.get("mode") in {None, "constant"}:
                continue
            upstream = port.get("src_id")
            if not isinstance(upstream, str):
                raise _IndexModelError(f"{source}.inport{index} lacks a named source")
            result.update(_collect_variables(upstream, config, visiting))
        return result
    raise _IndexModelError(f"unsupported index source {source!r}")


def _variable_domain(source: str, config: Mapping[str, Any]) -> tuple[int, ...]:
    if source.startswith("DRAM_LC."):
        loops = config.get("dram_loop_configs")
        name = source.split(".", 1)[1]
        loop = loops.get(name) if isinstance(loops, Mapping) else None
    else:
        match = re.fullmatch(r"(GROUP[0-4])\.(ROW_LC|COL_LC)", source)
        if match is None:
            raise _IndexModelError(f"unsupported loop source {source!r}")
        groups = config.get("buffer_loop_configs")
        group = groups.get(match.group(1)) if isinstance(groups, Mapping) else None
        loop = group.get(match.group(2)) if isinstance(group, Mapping) else None
    if not isinstance(loop, Mapping):
        raise _IndexModelError(f"missing loop {source}")
    start, end, stride = loop.get("start"), loop.get("end"), loop.get("stride")
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in (start, end, stride)):
        raise _IndexModelError(f"loop {source} start/end/stride must be integers")
    if stride <= 0 or start >= end:
        raise _IndexModelError(f"loop {source} does not progress")
    values = tuple(value & 0xFFFF for value in range(start, end, stride))
    if not values:
        raise _IndexModelError(f"loop {source} has an empty domain")
    return values


def _evaluate_source(
    source: str,
    config: Mapping[str, Any],
    environment: Mapping[str, int],
    visiting: set[str],
) -> int:
    if source in environment:
        return environment[source]
    if not source.startswith("LC_PE."):
        raise _IndexModelError(f"no value for {source}")
    if source in visiting:
        raise _IndexModelError(f"cycle in index expression at {source}")
    visiting = set(visiting)
    visiting.add(source)
    pes = config.get("lc_pe_configs")
    pe = pes.get(source.split(".", 1)[1]) if isinstance(pes, Mapping) else None
    if not isinstance(pe, Mapping):
        raise _IndexModelError(f"missing {source}")
    operands: list[int] = []
    for index in range(3):
        port = pe.get(f"inport{index}")
        if not isinstance(port, Mapping) or port.get("mode") is None:
            operands.append(0)
        elif port.get("mode") == "constant":
            operands.append(_constant16(port.get("constant", 0)))
        else:
            upstream = port.get("src_id")
            if not isinstance(upstream, str):
                raise _IndexModelError(f"{source}.inport{index} lacks source")
            operands.append(_evaluate_source(upstream, config, environment, visiting))
    signed = [_signed16(value) for value in operands]
    opcode = pe.get("alu_opcode")
    if opcode == "add":
        result = signed[0] + signed[1]
    elif opcode == "mul":
        result = signed[0] * signed[1]
    elif opcode == "mac":
        result = signed[0] * signed[1] + signed[2]
    else:
        raise _IndexModelError(f"unsupported LC_PE opcode {opcode!r} at {source}")
    return result & 0xFFFF


def _constant16(value: Any) -> int:
    if isinstance(value, str):
        text = value.strip()
        compact = text.replace(" ", "")
        if compact.lower().startswith("0x"):
            return int(compact, 16) & 0xFFFF
        if "/" in compact:
            numerator, denominator = compact.split("/", 1)
            value = float(Fraction(numerator)) / float(Fraction(denominator))
        else:
            value = float(Fraction(text))
    if isinstance(value, float):
        return int.from_bytes(struct.pack("<f", value), "little") & 0xFFFF
    return int(value) & 0xFFFF


def _signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _decode_byte_address(address: int, profile: TargetProfile) -> tuple[int, int, int]:
    slice_id = (address >> 25) & 0x1F
    bank = (address >> 23) & 0x3
    row = (address >> 10) & 0x1FFF
    column = (address >> 4) & 0x3F
    subword = address & 0xF
    offset = row * profile.ddr_columns * profile.subwords_per_column
    offset += column * profile.subwords_per_column + subword
    return slice_id, bank, offset


def _shape(value: Any, params: Mapping[str, int]) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("shape must be a non-empty array")
    result = tuple(_shape_dim(item, params) for item in value)
    if any(item <= 0 for item in result):
        raise ValueError("shape dimensions must be positive")
    return result


def _shape_dim(value: Any, params: Mapping[str, int]) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise ValueError("shape dimension must be an integer or expression")
    tree = ast.parse(value, mode="eval")

    def evaluate(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name) and node.id in params:
            return params[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv)):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ValueError("division by zero in shape")
            return left // right
        raise ValueError(f"unsupported shape expression {value!r}")

    return evaluate(tree)


def _positive_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("expected a positive integer")
    return value


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.replace("_", ""), 0)
        except ValueError as error:
            raise ValueError(f"invalid integer literal {value!r}") from error
    raise ValueError(f"expected integer literal, got {type(value).__name__}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_addresses(addresses: Sequence[int] | set[int]) -> str:
    digest = hashlib.sha256()
    for address in sorted(addresses):
        digest.update(f"{address:07X}\n".encode("ascii"))
    return digest.hexdigest()
