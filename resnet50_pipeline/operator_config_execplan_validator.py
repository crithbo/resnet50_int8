from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .operator_config_artifact_validator import OperatorConfigArtifactValidator
from .operator_config_validator import ConfigState, TargetProfile, ValidationIssue


COMMAND_RE = re.compile(r"^\s*(\d+)\s+<([01]{64})>\s+(.*)$")
LOAD_RE = re.compile(r"^Load_Config(?: SFU)? for operator ([^ ]+)")
START_RE = re.compile(r"^Start_Comp for operator ([^ ]+)")
PIPELINE_CONFIG_ARTIFACTS = (
    "mapping_review.json",
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
)


@dataclass(frozen=True)
class DecodedInstruction:
    index: int
    word: int
    opcode: int
    kind: str
    config_length: int | None = None
    ddr_config_addr: int | None = None
    config_sfu: bool | None = None
    slice_mask: int | None = None
    explained_operator: str | None = None


@dataclass
class ExecPlanConfigValidationReport:
    graph_root: str
    valid: bool
    issues: list[ValidationIssue]
    facts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "operator-config-execplan-validation-report-v1",
            "graph_root": self.graph_root,
            "valid": self.valid,
            "first_error": asdict(self.issues[0]) if self.issues else None,
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
        }


class OperatorConfigExecPlanValidator:
    """Bind native execplan Load_Config commands to strict JSON and bitstreams.

    The checker is independent of ndp-sim's instruction generator. It consumes
    the emitted graph, SCA manifest, 128-bit execplan, explanation stream,
    source JSON, mapping evidence and config artifacts as data.
    """

    def __init__(self, *, profile: TargetProfile | None = None) -> None:
        self.profile = profile or TargetProfile()
        self._issues: list[ValidationIssue] = []
        self._facts: dict[str, Any] = {}

    def validate(
        self,
        graph_root: Path,
        *,
        graph_path: Path,
        source_configs: Mapping[str, Path],
        mapping_evidence: Mapping[str, Mapping[str, Any]],
        artifact_dirs: Mapping[str, Path] | None = None,
    ) -> ExecPlanConfigValidationReport:
        self._issues = []
        self._facts = {"target_profile": asdict(self.profile)}
        root = graph_root.resolve()
        graph_path = graph_path.resolve()
        graph = self._load_json(graph_path, "EXECPLAN.GRAPH_PARSE", "$.graph")
        sca_path = root / "sca_cfg.json"
        sca = self._load_json(sca_path, "EXECPLAN.SCA_PARSE", "$.sca_cfg")
        operators = self._operators(graph)

        execplan_path = root / "install" / "execplan.txt"
        words, line_count = self._read_execplan(execplan_path)
        explanations = self._read_explanations(root / "instructions_explained.txt", words)
        decoded = [self._decode(index, word, explanations.get(index)) for index, word in enumerate(words)]

        if decoded:
            if decoded[0].kind != "Clock_Enable":
                self._error(
                    "EXECPLAN.CLOCK_ORDER",
                    "$.execplan[0]",
                    "the first real 64-bit command must be Clock_Enable",
                )
            else:
                expected_global = 0
                for operator in operators:
                    expected_global |= operator["used_slices"]
                if decoded[0].slice_mask != expected_global:
                    self._error(
                        "EXECPLAN.CLOCK_MASK",
                        "$.execplan[0]",
                        "Clock_Enable slice mask differs from the graph-wide union",
                    )

        if isinstance(sca, Mapping):
            exec_length = sca.get("Exec_Length")
            if exec_length != line_count:
                self._error(
                    "EXECPLAN.LENGTH",
                    "$.sca_cfg.Exec_Length",
                    f"expected {line_count} 128-bit lines, got {exec_length!r}",
                )

        loads = [item for item in decoded if item.kind == "Load_Config" and item.config_sfu is False]
        sfu_loads = [item for item in decoded if item.kind == "Load_Config" and item.config_sfu is True]
        starts = [item for item in decoded if item.kind == "Start_Comp"]
        if len(loads) != len(operators):
            self._error(
                "EXECPLAN.LOAD_COUNT",
                "$.execplan",
                f"graph has {len(operators)} operators but execplan has {len(loads)} non-SFU Load_Config commands",
            )
        if len(starts) != len(operators):
            self._error(
                "EXECPLAN.START_COUNT",
                "$.execplan",
                f"graph has {len(operators)} operators but execplan has {len(starts)} Start_Comp commands",
            )

        state = ConfigState()
        stage_facts: list[dict[str, Any]] = []
        stage_count = min(len(operators), len(loads), len(starts))
        dirs = artifact_dirs or {}
        for stage_index in range(stage_count):
            operator = operators[stage_index]
            op_id = operator["id"]
            load = loads[stage_index]
            start = starts[stage_index]
            path = f"$.stages[{stage_index}]"
            if not load.index < start.index:
                self._error(
                    "EXECPLAN.STAGE_ORDER",
                    path,
                    "Load_Config must precede the matching Start_Comp",
                )
            if stage_index + 1 < len(loads) and start.index > loads[stage_index + 1].index:
                self._error(
                    "EXECPLAN.STAGE_INTERLEAVE",
                    path,
                    "the next stage Load_Config appears before this stage Start_Comp",
                )
            if load.explained_operator != op_id or start.explained_operator != op_id:
                self._error(
                    "EXECPLAN.OPERATOR_BINDING",
                    path,
                    "instruction explanations do not bind Load_Config/Start_Comp to graph order",
                )
            if load.slice_mask != operator["used_slices"] or start.slice_mask != operator["used_slices"]:
                self._error(
                    "EXECPLAN.SLICE_MASK",
                    path,
                    "Load_Config/Start_Comp slice mask differs from the graph operator",
                )

            source_path = source_configs.get(op_id)
            if source_path is None:
                self._error("EXECPLAN.SOURCE_MISSING", path, f"no explicit source JSON for {op_id}")
                continue
            source_path = source_path.resolve()
            config = self._load_json(source_path, "EXECPLAN.SOURCE_PARSE", f"{path}.source_config")
            if not isinstance(config, Mapping):
                continue

            artifact_dir = dirs.get(op_id, root / "config" / op_id).resolve()
            evidence = mapping_evidence.get(op_id)
            artifact_report = OperatorConfigArtifactValidator().validate(
                config,
                artifact_dir,
                mapping_evidence=evidence,
                source=str(source_path),
                previous_state=state,
            )
            strict_valid = bool(
                artifact_report.facts.get("json_validation", {}).get("valid")
            )
            if strict_valid:
                state = artifact_report.next_state
            if not artifact_report.valid:
                first = artifact_report.issues[0] if artifact_report.issues else None
                detail = (
                    f"{first.code} at {first.path}: {first.message}"
                    if first is not None
                    else "artifact validation failed"
                )
                self._error("EXECPLAN.ARTIFACT_INVALID", f"{path}.artifact", detail)

            pipeline_binding = self._validate_pipeline_artifact_binding(
                root,
                op_id,
                operator["type"],
                source_path,
                artifact_dir,
                path,
            )

            binding = self._validate_sca_config_binding(
                root,
                sca,
                op_id,
                load,
                artifact_dir,
                path,
            )
            stage_facts.append(
                {
                    "stage_index": stage_index,
                    "op_id": op_id,
                    "op_type": operator["type"],
                    "load_instruction_index": load.index,
                    "start_instruction_index": start.index,
                    "slice_mask": f"0x{operator['used_slices']:07X}",
                    "source_config": str(source_path),
                    "source_config_sha256": _sha256_file(source_path),
                    "artifact_dir": str(artifact_dir),
                    "artifact_valid": artifact_report.valid,
                    "next_config_state": dict(artifact_report.next_state.fingerprints),
                    **pipeline_binding,
                    **binding,
                }
            )

        self._facts.update(
            {
                "graph": str(graph_path),
                "graph_sha256": _sha256_file(graph_path) if graph_path.is_file() else None,
                "execplan": str(execplan_path),
                "execplan_sha256": _sha256_file(execplan_path) if execplan_path.is_file() else None,
                "instruction_count_64bit": len(words),
                "execplan_lines_128bit": line_count,
                "operator_count": len(operators),
                "load_config_count": len(loads),
                "sfu_load_config_count": len(sfu_loads),
                "start_comp_count": len(starts),
                "stages": stage_facts,
                "final_config_state": dict(state.fingerprints),
                "issue_count": len(self._issues),
            }
        )
        return ExecPlanConfigValidationReport(
            graph_root=str(root),
            valid=not self._issues,
            issues=list(self._issues),
            facts=dict(self._facts),
        )

    def _operators(self, graph: Any) -> list[dict[str, Any]]:
        if not isinstance(graph, Mapping) or not isinstance(graph.get("operators"), list):
            self._error("EXECPLAN.GRAPH_SCHEMA", "$.graph.operators", "operators must be an array")
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(graph["operators"]):
            path = f"$.graph.operators[{index}]"
            if not isinstance(raw, Mapping):
                self._error("EXECPLAN.GRAPH_SCHEMA", path, "operator must be an object")
                continue
            op_id, op_type = raw.get("id"), raw.get("type")
            try:
                used_slices = _parse_int(raw.get("used_slices"))
            except ValueError as error:
                self._error("EXECPLAN.GRAPH_SCHEMA", f"{path}.used_slices", str(error))
                continue
            if not isinstance(op_id, str) or not op_id or not isinstance(op_type, str) or not op_type:
                self._error("EXECPLAN.GRAPH_SCHEMA", path, "id and type must be non-empty strings")
                continue
            if op_id in seen:
                self._error("EXECPLAN.GRAPH_SCHEMA", f"{path}.id", f"duplicate operator id {op_id}")
                continue
            if not 0 < used_slices < (1 << self.profile.slices):
                self._error("EXECPLAN.SLICE_MASK", f"{path}.used_slices", "mask exceeds target profile")
                continue
            seen.add(op_id)
            result.append({"id": op_id, "type": op_type, "used_slices": used_slices})
        return result

    def _read_execplan(self, path: Path) -> tuple[list[int], int]:
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, UnicodeError) as error:
            self._error("EXECPLAN.READ", str(path), str(error))
            return [], 0
        words: list[int] = []
        for index, line in enumerate(lines):
            if len(line) != 128 or set(line) - {"0", "1"}:
                self._error(
                    "EXECPLAN.LINE_FORMAT",
                    f"{path}:{index + 1}",
                    "each non-empty line must contain exactly 128 binary digits",
                )
                continue
            high, low = line[:64], line[64:]
            words.extend((int(low, 2), int(high, 2)))
        if words and words[-1] == 0:
            words.pop()
        return words, len(lines)

    def _read_explanations(self, path: Path, words: Sequence[int]) -> dict[int, str]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self._error("EXECPLAN.EXPLANATION_READ", str(path), str(error))
            return {}
        explanations: dict[int, str] = {}
        for line in lines:
            match = COMMAND_RE.match(line)
            if match is None:
                continue
            index = int(match.group(1))
            word = int(match.group(2), 2)
            if index in explanations:
                self._error("EXECPLAN.EXPLANATION_DUPLICATE", f"{path}:{index}", "duplicate command index")
                continue
            if index >= len(words) or words[index] != word:
                self._error(
                    "EXECPLAN.EXPLANATION_MISMATCH",
                    f"{path}:{index}",
                    "explained command bits do not match install/execplan.txt",
                )
            explanations[index] = match.group(3)
        if set(explanations) != set(range(len(words))):
            self._error(
                "EXECPLAN.EXPLANATION_COVERAGE",
                str(path),
                "instructions_explained.txt must cover every real 64-bit command exactly once",
            )
        return explanations

    def _decode(self, index: int, word: int, explanation: str | None) -> DecodedInstruction:
        opcode = word & 0b111
        explained_operator = None
        if explanation is not None:
            match = LOAD_RE.match(explanation) or START_RE.match(explanation)
            if match is not None:
                explained_operator = match.group(1)
        if opcode == 0:
            return DecodedInstruction(
                index=index,
                word=word,
                opcode=opcode,
                kind="Load_Config",
                config_length=(word >> 56) & 0xFF,
                ddr_config_addr=(word >> 34) & ((1 << 22) - 1),
                config_sfu=bool((word >> 31) & 1),
                slice_mask=(word >> 3) & ((1 << 28) - 1),
                explained_operator=explained_operator,
            )
        if opcode == 1:
            return DecodedInstruction(
                index, word, opcode, "Clock_Enable", slice_mask=(word >> 3) & ((1 << 28) - 1)
            )
        if opcode == 4:
            return DecodedInstruction(index, word, opcode, "Write_Reg", explained_operator=explained_operator)
        if opcode == 5:
            return DecodedInstruction(
                index,
                word,
                opcode,
                "Start_Comp",
                slice_mask=(word >> 3) & ((1 << 28) - 1),
                explained_operator=explained_operator,
            )
        self._error("EXECPLAN.OPCODE", f"$.execplan[{index}]", f"unsupported opcode {opcode:03b}")
        return DecodedInstruction(index, word, opcode, "Unknown", explained_operator=explained_operator)

    def _validate_pipeline_artifact_binding(
        self,
        root: Path,
        op_id: str,
        op_type: str,
        source_path: Path,
        artifact_dir: Path,
        stage_path: str,
    ) -> dict[str, Any]:
        """Bind planner-local JSON/mapping/bitstream files to validated evidence.

        It is not sufficient for ``sca_cfg`` to point at bytes which happen to
        equal a validated bitstream.  The files emitted by the same native
        planner run must also be identical to the hash-bound source JSON and
        mapping bundle; otherwise a stale or independently assembled execplan
        could be accepted.
        """

        generated_json = root / "jsons" / f"{op_id}_{op_type}.json"
        if not generated_json.is_file():
            self._error(
                "EXECPLAN.PIPELINE_SOURCE",
                f"{stage_path}.pipeline_json",
                f"missing native planner JSON {generated_json}",
            )
        else:
            try:
                generated_payload = json.loads(
                    generated_json.read_text(encoding="utf-8")
                )
                source_payload = json.loads(
                    source_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                self._error(
                    "EXECPLAN.PIPELINE_SOURCE",
                    f"{stage_path}.pipeline_json",
                    f"cannot compare planner/source JSON: {error}",
                )
            else:
                normalized_generated = _normalize_config_literals(
                    generated_payload
                )
                normalized_source = _normalize_config_literals(source_payload)
                if normalized_generated != normalized_source:
                    difference = _first_json_difference(
                        normalized_source, normalized_generated
                    )
                    self._error(
                        "EXECPLAN.PIPELINE_SOURCE",
                        f"{stage_path}.pipeline_json",
                        "native planner JSON differs from the hash-bound source "
                        f"config: {difference}",
                    )

        generated_artifacts = root / "config" / op_id
        hashes: dict[str, str | None] = {}
        for name in PIPELINE_CONFIG_ARTIFACTS:
            actual = generated_artifacts / name
            expected = artifact_dir / name
            actual_hash = _sha256_file(actual) if actual.is_file() else None
            expected_hash = _sha256_file(expected) if expected.is_file() else None
            hashes[name] = actual_hash
            if actual_hash is None or expected_hash is None or actual_hash != expected_hash:
                self._error(
                    "EXECPLAN.PIPELINE_ARTIFACT",
                    f"{stage_path}.pipeline_artifacts.{name}",
                    "native planner artifact differs from independently validated mapping evidence",
                )
        return {
            "pipeline_json": str(generated_json),
            "pipeline_json_sha256": (
                _sha256_file(generated_json) if generated_json.is_file() else None
            ),
            "pipeline_artifact_sha256": hashes,
        }

    def _validate_sca_config_binding(
        self,
        root: Path,
        sca: Any,
        op_id: str,
        load: DecodedInstruction,
        artifact_dir: Path,
        stage_path: str,
    ) -> dict[str, Any]:
        if not isinstance(sca, Mapping):
            return {}
        entry = sca.get(f"{op_id}_config")
        if not isinstance(entry, Mapping):
            self._error("EXECPLAN.SCA_CONFIG", f"{stage_path}.sca", f"missing {op_id}_config entry")
            return {}
        try:
            base_addr = _parse_int(entry.get("base_addr"))
        except ValueError as error:
            self._error("EXECPLAN.SCA_CONFIG", f"{stage_path}.sca.base_addr", str(error))
            return {}
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            self._error("EXECPLAN.SCA_CONFIG", f"{stage_path}.sca.path", "path must be a non-empty string")
            return {}
        try:
            config_path = _safe_child(root, relative)
        except ValueError as error:
            self._error("EXECPLAN.SCA_CONFIG", f"{stage_path}.sca.path", str(error))
            return {}
        if base_addr & 0x3FF:
            self._error("EXECPLAN.CONFIG_ALIGNMENT", f"{stage_path}.sca.base_addr", "config base must be 1024-byte aligned")
        if load.ddr_config_addr != base_addr >> 10:
            self._error(
                "EXECPLAN.CONFIG_ADDRESS",
                stage_path,
                "Load_Config compressed DDR address differs from sca_cfg base_addr",
            )
        try:
            config_length = _bitstream_word_length(config_path)
        except (OSError, UnicodeError, ValueError) as error:
            self._error("EXECPLAN.CONFIG_FILE", f"{stage_path}.sca.path", str(error))
            return {"config_path": str(config_path)}
        if load.config_length != config_length:
            self._error(
                "EXECPLAN.CONFIG_LENGTH",
                stage_path,
                f"Load_Config length {load.config_length} differs from bitstream length {config_length}",
            )
        artifact_128 = artifact_dir / "modules_dump_128b.bin"
        if not artifact_128.is_file() or not config_path.is_file() or _sha256_file(artifact_128) != _sha256_file(config_path):
            self._error(
                "EXECPLAN.CONFIG_ARTIFACT_BINDING",
                stage_path,
                "sca_cfg config payload differs from the independently validated 128-bit artifact",
            )
        return {
            "config_base_addr": f"0x{base_addr:08X}",
            "config_length_64bit_words": config_length,
            "config_path": str(config_path),
            "config_sha256": _sha256_file(config_path) if config_path.is_file() else None,
        }

    def _load_json(self, path: Path, code: str, issue_path: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._error(code, issue_path, str(error))
            return None

    def _error(self, code: str, path: str, message: str) -> None:
        self._issues.append(ValidationIssue(code, path, message))


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer address/mask")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.replace("_", "")
        try:
            return int(normalized, 0)
        except ValueError as error:
            raise ValueError(f"invalid integer literal {value!r}") from error
    raise ValueError(f"expected integer literal, got {type(value).__name__}")


def _first_json_difference(expected: Any, actual: Any, path: str = "$") -> str:
    if type(expected) is not type(actual):
        return (
            f"{path} type {type(expected).__name__} != "
            f"{type(actual).__name__}"
        )
    if isinstance(expected, Mapping):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing:
            return f"{path} missing key {missing[0]!r}"
        if extra:
            return f"{path} extra key {extra[0]!r}"
        for key in expected:
            if expected[key] != actual[key]:
                return _first_json_difference(
                    expected[key], actual[key], f"{path}.{key}"
                )
        return f"{path} object differs"
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path} length {len(expected)} != {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            if left != right:
                return _first_json_difference(
                    left, right, f"{path}[{index}]"
                )
        return f"{path} list differs"
    return f"{path} expected {expected!r}, got {actual!r}"


def _normalize_config_literals(value: Any, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {
            item_key: _normalize_config_literals(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_config_literals(item, key) for item in value]
    if key == "base_addr":
        try:
            return _parse_int(value)
        except ValueError:
            return value
    return value


def _safe_child(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must be relative and remain under graph root")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes graph root") from error
    return resolved


def _bitstream_word_length(path: Path) -> int:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("config bitstream is empty")
    widths = {len(line) for line in lines}
    if len(widths) != 1 or next(iter(widths)) not in {64, 128}:
        raise ValueError("config bitstream lines must be uniformly 64 or 128 bits")
    if any(set(line) - {"0", "1"} for line in lines):
        raise ValueError("config bitstream contains non-binary data")
    return len(lines) * (2 if next(iter(widths)) == 128 else 1)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
