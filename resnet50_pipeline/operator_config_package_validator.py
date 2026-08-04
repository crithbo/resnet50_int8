from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .operator_config_validator import TargetProfile, ValidationIssue


MATRIX_KEY_RE = re.compile(
    r"^(?P<op>.+)_matrix(?P<tensor>A|B|Bp|C|D)_slice(?P<slice>\d+)(?:_(?P<bank>\d+))?$"
)
BP_INDEPENDENT_OPS = {"decode_gemv_ring", "decode_gemv_local"}
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


@dataclass(frozen=True)
class MemoryRegion:
    key: str
    storage_id: str
    kind: str
    slice_id: int
    bank: int
    start: int
    end: int
    base_addr: int
    length_bytes: int


@dataclass
class PackageValidationReport:
    graph_root: str
    valid: bool
    issues: list[ValidationIssue]
    facts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "operator-config-package-validation-report-v1",
            "graph_root": self.graph_root,
            "valid": self.valid,
            "first_error": asdict(self.issues[0]) if self.issues else None,
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
        }


class OperatorConfigPackageValidator:
    """Validate native SCA memory layout and a hash-bound semantic contract.

    This checker intentionally does not import ``ndp-sim``.  It decodes the
    30-bit physical address directly, reconstructs expected matrix entries
    from the graph, checks aliases and occupied spans, and rejects a row equal
    to the profile limit instead of inheriting the native planner's 8192-row
    constant.
    """

    def __init__(self, *, profile: TargetProfile | None = None) -> None:
        self.profile = profile or TargetProfile()
        self._issues: list[ValidationIssue] = []

    def validate(
        self,
        graph_root: Path,
        *,
        graph_path: Path,
        semantic_contract: Mapping[str, Any] | None = None,
        require_matrix_files: bool = True,
        provenance_root: Path | None = None,
    ) -> PackageValidationReport:
        self._issues = []
        root = graph_root.resolve()
        graph_path = graph_path.resolve()
        graph = self._load_json(graph_path, "PACKAGE.GRAPH_PARSE", "$.graph")
        sca = self._load_json(root / "sca_cfg.json", "PACKAGE.SCA_PARSE", "$.sca_cfg")
        sca_d = self._load_json(
            root / "sca_cfg_D.json", "PACKAGE.SCA_D_PARSE", "$.sca_cfg_D"
        )
        operators, params = self._operators(graph)
        contract_facts = self._validate_contract(
            graph_path,
            operators,
            params,
            semantic_contract,
            (provenance_root or root).resolve(),
        )

        entries: dict[str, Mapping[str, Any]] = {}
        if isinstance(sca, Mapping):
            entries.update(
                (str(key), value)
                for key, value in sca.items()
                if isinstance(value, Mapping)
            )
        if isinstance(sca_d, Mapping):
            for key, value in sca_d.items():
                if key in entries:
                    self._error("SCA.DUPLICATE_KEY", f"$.sca_cfg_D.{key}", "key also exists in sca_cfg.json")
                if isinstance(value, Mapping):
                    entries[str(key)] = value

        expected = self._expected_matrix_entries(operators, params)
        actual_matrix = {key for key in entries if MATRIX_KEY_RE.fullmatch(key)}
        for key in sorted(set(expected) - actual_matrix):
            code = "SCA.B_PRIME_MISSING" if "_matrixBp_" in key else "SCA.MATRIX_MISSING"
            self._error(code, f"$.sca.{key}", "required graph tensor entry is missing")
        for key in sorted(actual_matrix - set(expected)):
            self._error("SCA.MATRIX_UNEXPECTED", f"$.sca.{key}", "entry is not declared by the graph")

        regions: list[MemoryRegion] = []
        file_facts: dict[str, dict[str, Any]] = {}
        missing_files: list[str] = []
        for key, metadata in sorted(expected.items()):
            entry = entries.get(key)
            if not isinstance(entry, Mapping):
                continue
            region = self._matrix_region(key, entry, metadata, root)
            if region is not None:
                regions.append(region)
            file_fact = self._validate_entry_path(
                root,
                key,
                entry,
                expected_bytes=metadata["length_bytes"],
                require=require_matrix_files,
            )
            file_facts[key] = file_fact
            if not file_fact.get("exists"):
                missing_files.append(key)

        control_regions = self._control_regions(root, sca, entries)
        regions.extend(control_regions)
        self._validate_aliases_and_overlap(regions)
        self._validate_graph_base_addresses(operators, params, entries)

        facts = {
            "target_profile": asdict(self.profile),
            "graph": str(graph_path),
            "graph_sha256": _sha256_file(graph_path) if graph_path.is_file() else None,
            "operator_count": len(operators),
            "expected_matrix_entry_count": len(expected),
            "actual_matrix_entry_count": len(actual_matrix),
            "memory_region_count": len(regions),
            "peak_end_by_slice_bank": self._peak_by_slice_bank(regions),
            "matrix_files_required": require_matrix_files,
            "missing_matrix_files": missing_files,
            "file_facts": file_facts,
            "semantic_contract": contract_facts,
            "issue_count": len(self._issues),
        }
        return PackageValidationReport(
            graph_root=str(root),
            valid=not self._issues,
            issues=list(self._issues),
            facts=facts,
        )

    def _operators(self, graph: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not isinstance(graph, Mapping):
            self._error("PACKAGE.GRAPH_SCHEMA", "$.graph", "graph must be an object")
            return [], {}
        raw_params = graph.get("params", {})
        params = {
            str(key): value
            for key, value in raw_params.items()
            if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
        } if isinstance(raw_params, Mapping) else {}
        raw_ops = graph.get("operators")
        if not isinstance(raw_ops, list):
            self._error("PACKAGE.GRAPH_SCHEMA", "$.graph.operators", "operators must be an array")
            return [], params
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_ops):
            path = f"$.graph.operators[{index}]"
            if not isinstance(raw, Mapping):
                self._error("PACKAGE.GRAPH_SCHEMA", path, "operator must be an object")
                continue
            op_id, op_type = raw.get("id"), raw.get("type")
            if not isinstance(op_id, str) or not op_id or not isinstance(op_type, str) or not op_type:
                self._error("PACKAGE.GRAPH_SCHEMA", path, "id and type must be non-empty strings")
                continue
            if op_id in seen:
                self._error("PACKAGE.GRAPH_SCHEMA", f"{path}.id", "duplicate operator id")
                continue
            try:
                mask = _parse_int(raw.get("used_slices"))
            except ValueError as error:
                self._error("PACKAGE.GRAPH_SCHEMA", f"{path}.used_slices", str(error))
                continue
            if not 0 < mask < (1 << self.profile.slices):
                self._error("PACKAGE.SLICE_MASK", f"{path}.used_slices", "mask exceeds target profile")
                continue
            inputs = raw.get("inputs")
            output = raw.get("output", raw.get("D"))
            if not isinstance(inputs, Mapping) or not isinstance(output, Mapping):
                self._error("PACKAGE.GRAPH_SCHEMA", path, "inputs and output must be objects")
                continue
            seen.add(op_id)
            result.append(
                {
                    "id": op_id,
                    "type": op_type,
                    "mask": mask,
                    "inputs": dict(inputs),
                    "output": dict(output),
                }
            )
        return result, params

    def _expected_matrix_entries(
        self, operators: list[dict[str, Any]], params: Mapping[str, int]
    ) -> dict[str, dict[str, Any]]:
        expected: dict[str, dict[str, Any]] = {}
        for op in operators:
            slices = [index for index in range(self.profile.slices) if (op["mask"] >> index) & 1]
            for tensor_name, tensor in op["inputs"].items():
                if tensor_name not in {"A", "B", "B'", "C"} or not isinstance(tensor, Mapping):
                    continue
                if tensor_name == "B'" and op["type"] not in BP_INDEPENDENT_OPS:
                    continue
                manifest_name = "Bp" if tensor_name == "B'" else tensor_name
                storage_id = self._input_storage_id(op, tensor_name, tensor)
                self._add_expected_tensor(
                    expected, op, manifest_name, tensor, slices, params, storage_id, output=False
                )
            self._add_expected_tensor(
                expected,
                op,
                "D",
                op["output"],
                slices,
                params,
                f"{op['id']}.output.D",
                output=True,
            )
        return expected

    def _add_expected_tensor(
        self,
        expected: dict[str, dict[str, Any]],
        op: Mapping[str, Any],
        manifest_name: str,
        tensor: Mapping[str, Any],
        slices: list[int],
        params: Mapping[str, int],
        storage_id: str,
        *,
        output: bool,
    ) -> None:
        path = f"$.graph.{op['id']}.{manifest_name}"
        try:
            shape = _shape(tensor.get("shape"), params)
            dtype = str(tensor.get("dtype", "fp32")).lower()
            size = math.prod(shape) * DTYPE_BYTES[dtype]
            interleave = _positive_int(tensor.get("bank_interleave", 1))
        except (KeyError, TypeError, ValueError) as error:
            self._error("PACKAGE.TENSOR_SCHEMA", path, str(error))
            return
        if interleave not in {1, 2, 4} or self.profile.banks_per_slice % interleave:
            self._error("PACKAGE.BANK_INTERLEAVE", path, "bank_interleave must divide target banks")
            return
        if size % interleave:
            self._error("PACKAGE.BANK_INTERLEAVE", path, "tensor bytes are not divisible by bank_interleave")
            return
        per_bank = size // interleave
        allocated = _align_up(per_bank, 16)
        for slice_id in slices:
            for bank_offset in range(interleave):
                suffix = f"_{bank_offset}" if interleave > 1 else ""
                key = f"{op['id']}_matrix{manifest_name}_slice{slice_id}{suffix}"
                expected[key] = {
                    "op_id": op["id"],
                    "tensor": manifest_name,
                    "slice_id": slice_id,
                    "bank_offset": bank_offset,
                    "bank_interleave": interleave,
                    "storage_id": storage_id,
                    "length_bytes": allocated,
                    "length_words_128b": allocated // 16,
                    "output": output,
                }

    def _matrix_region(
        self,
        key: str,
        entry: Mapping[str, Any],
        metadata: Mapping[str, Any],
        root: Path,
    ) -> MemoryRegion | None:
        path = f"$.sca.{key}"
        try:
            address = _parse_int(entry.get("base_addr"))
        except ValueError as error:
            self._error("SCA.ADDRESS_FORMAT", f"{path}.base_addr", str(error))
            return None
        decoded = self._validate_address(address, f"{path}.base_addr", metadata["length_bytes"])
        if decoded is None:
            return None
        slice_id, bank, offset = decoded
        if slice_id != metadata["slice_id"]:
            self._error("SCA.SLICE_ADDRESS", f"{path}.base_addr", "encoded slice differs from manifest key")
        if metadata["bank_interleave"] > 1:
            first_key = re.sub(r"_\d+$", "_0", key)
            first_entry = self._entry_for_key(root, first_key)
            if isinstance(first_entry, Mapping):
                try:
                    first_bank = (_parse_int(first_entry.get("base_addr")) >> 23) & 0x3
                    if bank != first_bank + metadata["bank_offset"]:
                        self._error("SCA.BANK_ADDRESS", f"{path}.base_addr", "bank suffix does not match encoded bank")
                except ValueError:
                    pass
        if metadata["output"]:
            length = entry.get("length")
            if length != metadata["length_words_128b"]:
                self._error(
                    "SCA.OUTPUT_LENGTH",
                    f"{path}.length",
                    f"expected {metadata['length_words_128b']} 128-bit words, got {length!r}",
                )
        return MemoryRegion(
            key=key,
            storage_id=f"{metadata['storage_id']}:bank{metadata['bank_offset']}",
            kind="matrix",
            slice_id=slice_id,
            bank=bank,
            start=offset,
            end=offset + metadata["length_bytes"],
            base_addr=address,
            length_bytes=metadata["length_bytes"],
        )

    def _control_regions(
        self, root: Path, sca: Any, entries: Mapping[str, Mapping[str, Any]]
    ) -> list[MemoryRegion]:
        regions: list[MemoryRegion] = []
        if not isinstance(sca, Mapping):
            return regions
        exec_entry = sca.get("ExecutionPlan")
        exec_length = sca.get("Exec_Length")
        if isinstance(exec_entry, Mapping) and isinstance(exec_length, int) and exec_length > 0:
            region = self._control_region(root, "ExecutionPlan", exec_entry, exec_length * 16)
            if region:
                regions.append(region)
        else:
            self._error("SCA.EXEC", "$.sca_cfg.ExecutionPlan", "execution plan entry/length is missing")
        for key, entry in sorted(entries.items()):
            if not (key.endswith("_config") or key.endswith("_sfu_config")):
                continue
            file_fact = self._validate_entry_path(root, key, entry, expected_bytes=None, require=True)
            length = file_fact.get("binary_bytes")
            if not isinstance(length, int) or length <= 0:
                continue
            region = self._control_region(root, key, entry, length)
            if region:
                regions.append(region)
        return regions

    def _control_region(
        self, root: Path, key: str, entry: Mapping[str, Any], length: int
    ) -> MemoryRegion | None:
        try:
            address = _parse_int(entry.get("base_addr"))
        except ValueError as error:
            self._error("SCA.ADDRESS_FORMAT", f"$.sca.{key}.base_addr", str(error))
            return None
        decoded = self._validate_address(address, f"$.sca.{key}.base_addr", length)
        if decoded is None:
            return None
        slice_id, bank, offset = decoded
        if slice_id != 0:
            self._error("SCA.CONTROL_SLICE", f"$.sca.{key}.base_addr", "control payload must reside in slice 0")
        self._validate_entry_path(root, key, entry, expected_bytes=length, require=True)
        return MemoryRegion(
            key=key,
            storage_id=f"control:{key}",
            kind="control",
            slice_id=slice_id,
            bank=bank,
            start=offset,
            end=offset + length,
            base_addr=address,
            length_bytes=length,
        )

    def _validate_address(
        self, address: int, path: str, length: int
    ) -> tuple[int, int, int] | None:
        if not 0 <= address < (1 << 30):
            self._error("SCA.ADDRESS_RANGE", path, "address must fit unsigned 30 bits")
            return None
        slice_id = (address >> 25) & 0x1F
        bank = (address >> 23) & 0x3
        row = (address >> 10) & 0x1FFF
        column = (address >> 4) & 0x3F
        subword = address & 0xF
        if slice_id >= self.profile.slices or bank >= self.profile.banks_per_slice:
            self._error("SCA.ADDRESS_PROFILE", path, "slice or bank exceeds target profile")
        if row >= self.profile.ddr_rows:
            self._error("SCA.ROW_LIMIT", path, f"row {row} must be < {self.profile.ddr_rows}")
        if column >= self.profile.ddr_columns or subword >= self.profile.subwords_per_column:
            self._error("SCA.ADDRESS_PROFILE", path, "column or subword exceeds target profile")
        if subword != 0:
            self._error("SCA.ALIGNMENT", path, "base address must be 128-bit aligned")
        offset = row * self.profile.ddr_columns * self.profile.subwords_per_column + column * self.profile.subwords_per_column + subword
        bank_capacity = self.profile.ddr_rows * self.profile.ddr_columns * self.profile.subwords_per_column
        if offset + length > bank_capacity:
            self._error("SCA.CAPACITY", path, "region crosses the target bank row limit")
        return slice_id, bank, offset

    def _validate_entry_path(
        self,
        root: Path,
        key: str,
        entry: Mapping[str, Any],
        *,
        expected_bytes: int | None,
        require: bool,
    ) -> dict[str, Any]:
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            self._error("SCA.PATH", f"$.sca.{key}.path", "path must be a non-empty string")
            return {"exists": False}
        try:
            path = _safe_child(root, relative)
        except ValueError as error:
            self._error("SCA.PATH", f"$.sca.{key}.path", str(error))
            return {"exists": False, "path": relative}
        exists = path.is_file()
        if require and not exists:
            self._error("SCA.FILE_MISSING", f"$.sca.{key}.path", f"missing file {path}")
        fact: dict[str, Any] = {"path": str(path), "exists": exists}
        if not exists:
            return fact
        fact["sha256"] = _sha256_file(path)
        try:
            binary_bytes = _binary_text_size(path)
        except (OSError, UnicodeError, ValueError) as error:
            self._error("SCA.FILE_FORMAT", f"$.sca.{key}.path", str(error))
            return fact
        fact["binary_bytes"] = binary_bytes
        if expected_bytes is not None and binary_bytes != expected_bytes:
            self._error(
                "SCA.FILE_LENGTH",
                f"$.sca.{key}.path",
                f"expected {expected_bytes} bytes, got {binary_bytes}",
            )
        return fact

    def _validate_aliases_and_overlap(self, regions: list[MemoryRegion]) -> None:
        ordered = sorted(regions, key=lambda item: (item.slice_id, item.bank, item.start, item.end, item.key))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if (left.slice_id, left.bank) != (right.slice_id, right.bank):
                    if (right.slice_id, right.bank) > (left.slice_id, left.bank):
                        break
                    continue
                if right.start >= left.end:
                    break
                if left.storage_id != right.storage_id:
                    self._error(
                        "SCA.REGION_OVERLAP",
                        f"$.regions.{right.key}",
                        f"overlaps {left.key} without a declared alias",
                    )
                elif (left.start, left.end) != (right.start, right.end):
                    self._error(
                        "SCA.ALIAS_SPAN",
                        f"$.regions.{right.key}",
                        f"declared alias span differs from {left.key}",
                    )

    def _validate_graph_base_addresses(
        self,
        operators: list[dict[str, Any]],
        params: Mapping[str, int],
        entries: Mapping[str, Mapping[str, Any]],
    ) -> None:
        del params
        for op in operators:
            for tensor_name, tensor in op["inputs"].items():
                if not isinstance(tensor, Mapping) or "base_addr" not in tensor:
                    self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.inputs.{tensor_name}.base_addr", "withbaseaddr graph is missing base_addr")
                    continue
                manifest_name = "B" if tensor_name == "B'" and op["type"] not in BP_INDEPENDENT_OPS else "Bp" if tensor_name == "B'" else tensor_name
                suffix = "_0" if tensor.get("bank_interleave", 1) > 1 else ""
                key = f"{op['id']}_matrix{manifest_name}_slice0{suffix}"
                entry = entries.get(key)
                if isinstance(entry, Mapping):
                    try:
                        if _parse_int(tensor["base_addr"]) != _parse_int(entry.get("base_addr")):
                            self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.inputs.{tensor_name}.base_addr", f"differs from {key}")
                    except ValueError as error:
                        self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.inputs.{tensor_name}.base_addr", str(error))
            output = op["output"]
            if "base_addr" not in output:
                self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.output.base_addr", "withbaseaddr graph is missing base_addr")
                continue
            suffix = "_0" if output.get("bank_interleave", 1) > 1 else ""
            key = f"{op['id']}_matrixD_slice0{suffix}"
            entry = entries.get(key)
            if isinstance(entry, Mapping):
                try:
                    if _parse_int(output["base_addr"]) != _parse_int(entry.get("base_addr")):
                        self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.output.base_addr", f"differs from {key}")
                except ValueError as error:
                    self._error("SCA.GRAPH_BASE", f"$.graph.{op['id']}.output.base_addr", str(error))

    def _validate_contract(
        self,
        graph_path: Path,
        operators: list[dict[str, Any]],
        params: Mapping[str, int],
        contract: Mapping[str, Any] | None,
        provenance_root: Path,
    ) -> dict[str, Any]:
        if not isinstance(contract, Mapping):
            self._error("CONTRACT.MISSING", "$.semantic_contract", "hash-bound qparam/layout/stage/provenance contract is required")
            return {"bound": False}
        if contract.get("schema") != "operator-config-semantic-contract-v1":
            self._error("CONTRACT.SCHEMA", "$.semantic_contract.schema", "unsupported semantic contract schema")
        expected_hash = contract.get("graph_sha256")
        actual_hash = _sha256_file(graph_path) if graph_path.is_file() else None
        if expected_hash != actual_hash:
            self._error("CONTRACT.GRAPH_IDENTITY", "$.semantic_contract.graph_sha256", "contract is not bound to this graph")
        profile = contract.get("target_profile")
        if profile != asdict(self.profile):
            self._error("CONTRACT.PROFILE", "$.semantic_contract.target_profile", "target profile differs from validator profile")
        raw_ops = contract.get("operators")
        if not isinstance(raw_ops, Mapping) or set(raw_ops) != {op["id"] for op in operators}:
            self._error("CONTRACT.OPERATORS", "$.semantic_contract.operators", "operator ids must exactly match graph")
            return {"bound": False, "graph_sha256": actual_hash}
        for op in operators:
            item = raw_ops.get(op["id"])
            path = f"$.semantic_contract.operators.{op['id']}"
            if not isinstance(item, Mapping) or item.get("op_type") != op["type"]:
                self._error("CONTRACT.OPERATOR", path, "operator type differs from graph")
                continue
            layouts = item.get("layouts")
            names = set(op["inputs"]) | {"D"}
            if not isinstance(layouts, Mapping) or set(layouts) != names or any(
                not isinstance(layouts.get(name), str) or not layouts.get(name)
                for name in names
            ):
                self._error("CONTRACT.LAYOUT", f"{path}.layouts", "every graph tensor requires one non-empty layout")
            qparams = item.get("qparams")
            quantized = any(
                str(tensor.get("dtype", "fp32")).lower() in {"int8", "uint8"}
                for tensor in [*op["inputs"].values(), op["output"]]
                if isinstance(tensor, Mapping)
            )
            if not isinstance(qparams, Mapping):
                self._error("CONTRACT.QPARAM", f"{path}.qparams", "qparam policy is required")
            elif quantized and qparams.get("policy") != "explicit":
                self._error("CONTRACT.QPARAM", f"{path}.qparams.policy", "quantized tensors require explicit qparam bindings")
            elif quantized:
                bindings = qparams.get("bindings")
                quantized_names = {
                    name
                    for name, tensor in {**op["inputs"], "D": op["output"]}.items()
                    if isinstance(tensor, Mapping)
                    and str(tensor.get("dtype", "fp32")).lower() in {"int8", "uint8"}
                }
                if not isinstance(bindings, Mapping) or set(bindings) != quantized_names:
                    self._error("CONTRACT.QPARAM", f"{path}.qparams.bindings", "every quantized tensor requires one binding")
                else:
                    for name, binding in bindings.items():
                        if not isinstance(binding, Mapping):
                            self._error("CONTRACT.QPARAM", f"{path}.qparams.bindings.{name}", "binding must be an object")
                            continue
                        scale, zero_point, source = binding.get("scale"), binding.get("zero_point"), binding.get("source")
                        self._validate_qparam_value(
                            scale,
                            kind="scale",
                            path=f"{path}.qparams.bindings.{name}.scale",
                        )
                        self._validate_qparam_value(
                            zero_point,
                            kind="zero_point",
                            path=f"{path}.qparams.bindings.{name}.zero_point",
                        )
                        if not isinstance(source, str) or not source:
                            self._error("CONTRACT.QPARAM", f"{path}.qparams.bindings.{name}.source", "qparam source is required")
            elif not quantized and qparams.get("policy") != "not-applicable":
                self._error("CONTRACT.QPARAM", f"{path}.qparams.policy", "non-quantized operator must explicitly declare not-applicable")
            stage = item.get("stage")
            if not isinstance(stage, Mapping) or not isinstance(stage.get("role"), str) or not isinstance(stage.get("dependencies"), list):
                self._error("CONTRACT.STAGE", f"{path}.stage", "stage role and dependency array are required")
            elif set(stage["dependencies"]) != self._graph_dependencies(op):
                self._error("CONTRACT.STAGE", f"{path}.stage.dependencies", "dependencies differ from operator-sourced graph inputs")
            provenance = item.get("provenance")
            if not isinstance(provenance, Mapping):
                self._error("CONTRACT.PROVENANCE", f"{path}.provenance", "source config and mapping evidence artifacts are required")
            else:
                for name in ("source_config", "mapping_evidence"):
                    self._validate_provenance_item(
                        provenance_root,
                        provenance.get(name),
                        f"{path}.provenance.{name}",
                    )
            tail = item.get("tail")
            if not isinstance(tail, Mapping) or tail.get("policy") not in {"exact", "explicit"}:
                self._error("CONTRACT.TAIL", f"{path}.tail", "tail policy must be exact or explicit")
            elif tail.get("policy") == "explicit":
                self._validate_tail_bindings(op, params, tail, f"{path}.tail")
        return {"bound": True, "graph_sha256": actual_hash, "operator_count": len(raw_ops)}

    def _validate_qparam_value(self, raw: Any, *, kind: str, path: str) -> None:
        """Accept a scalar or a hash-bound typed tensor qparam.

        Scalar bindings remain backward compatible with the original semantic
        contract.  Per-channel quantization must preserve the typed lowering
        identity instead of collapsing the vector to an invented scalar.
        """

        if kind == "scale" and isinstance(raw, (int, float)) and not isinstance(raw, bool):
            if not math.isfinite(float(raw)) or raw <= 0:
                self._error("CONTRACT.QPARAM", path, "scale must be finite and positive")
            return
        if kind == "zero_point" and isinstance(raw, int) and not isinstance(raw, bool):
            return
        if not isinstance(raw, Mapping):
            expected = "positive scalar or typed tensor" if kind == "scale" else "integer scalar or typed tensor"
            self._error("CONTRACT.QPARAM", path, f"{kind} must be an {expected}")
            return

        value_kind = raw.get("value_kind")
        dtype = raw.get("dtype")
        shape = raw.get("shape")
        element_count = raw.get("element_count")
        value_sha256 = raw.get("value_sha256")
        if value_kind not in {"scalar", "per_channel"}:
            self._error("CONTRACT.QPARAM", f"{path}.value_kind", "must be scalar or per_channel")
        if kind == "scale":
            if dtype not in {"float16", "float32", "float64"}:
                self._error("CONTRACT.QPARAM", f"{path}.dtype", "scale tensor dtype must be floating-point")
        elif not isinstance(dtype, str) or not re.fullmatch(r"u?int(8|16|32|64)", dtype):
            self._error("CONTRACT.QPARAM", f"{path}.dtype", "zero-point tensor dtype must be integer")
        if (
            not isinstance(shape, list)
            or not shape
            or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
        ):
            self._error("CONTRACT.QPARAM", f"{path}.shape", "shape must contain positive integers")
        elif (
            isinstance(element_count, bool)
            or not isinstance(element_count, int)
            or element_count != math.prod(shape)
        ):
            self._error("CONTRACT.QPARAM", f"{path}.element_count", "element count must equal shape product")
        if not isinstance(value_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", value_sha256):
            self._error("CONTRACT.QPARAM", f"{path}.value_sha256", "typed tensor requires lowercase SHA-256")

        if value_kind == "scalar":
            scalar = raw.get("scalar")
            if shape != [1] or element_count != 1:
                self._error("CONTRACT.QPARAM", path, "scalar tensor must have shape [1] and one element")
            if kind == "scale":
                if (
                    not isinstance(scalar, (int, float))
                    or isinstance(scalar, bool)
                    or not math.isfinite(float(scalar))
                    or scalar <= 0
                ):
                    self._error("CONTRACT.QPARAM", f"{path}.scalar", "scale scalar must be finite and positive")
            elif not isinstance(scalar, int) or isinstance(scalar, bool):
                self._error("CONTRACT.QPARAM", f"{path}.scalar", "zero-point scalar must be an integer")
            return

        axis = raw.get("axis")
        minimum, maximum = raw.get("minimum"), raw.get("maximum")
        if (
            not isinstance(axis, int)
            or isinstance(axis, bool)
            or not isinstance(shape, list)
            or axis < 0
            or axis >= len(shape)
            or not isinstance(element_count, int)
            or shape[axis] != element_count
        ):
            self._error("CONTRACT.QPARAM", f"{path}.axis", "per-channel axis must own every tensor element")
        if kind == "scale":
            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                for value in (minimum, maximum)
            ) or float(minimum) <= 0 or float(maximum) < float(minimum):
                self._error("CONTRACT.QPARAM", path, "per-channel scale range must be finite and positive")
        elif (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or maximum < minimum
        ):
            self._error("CONTRACT.QPARAM", path, "per-channel zero-point range must contain integers")

    def _validate_tail_bindings(
        self,
        op: Mapping[str, Any],
        params: Mapping[str, int],
        tail: Mapping[str, Any],
        path: str,
    ) -> None:
        bindings = tail.get("bindings")
        tensors = {**op["inputs"], "D": op["output"]}
        if not isinstance(bindings, Mapping) or set(bindings) != set(tensors):
            self._error("CONTRACT.TAIL", f"{path}.bindings", "explicit tail policy requires every tensor")
            return
        for name, tensor in tensors.items():
            binding = bindings.get(name)
            item_path = f"{path}.bindings.{name}"
            if not isinstance(tensor, Mapping) or not isinstance(binding, Mapping):
                self._error("CONTRACT.TAIL", item_path, "tail binding must be an object")
                continue
            try:
                logical = math.prod(_shape(tensor.get("shape"), params))
                block = _positive_int(binding.get("block_elements"))
                valid_last = _positive_int(binding.get("valid_last"))
            except (TypeError, ValueError) as error:
                self._error("CONTRACT.TAIL", item_path, str(error))
                continue
            expected = logical % block or block
            if valid_last > block or valid_last != expected:
                self._error(
                    "CONTRACT.TAIL_RANGE",
                    f"{item_path}.valid_last",
                    f"expected {expected} of block {block}, got {valid_last}",
                )

    @staticmethod
    def _graph_dependencies(op: Mapping[str, Any]) -> set[str]:
        result: set[str] = set()
        for tensor in op["inputs"].values():
            if not isinstance(tensor, Mapping):
                continue
            source = tensor.get("source")
            if isinstance(source, Mapping) and source.get("type") == "operator":
                producer = source.get("operator_id")
                if isinstance(producer, str) and producer:
                    result.add(producer)
        return result

    def _validate_provenance_item(
        self, root: Path, raw: Any, path: str
    ) -> None:
        if not isinstance(raw, Mapping):
            self._error("CONTRACT.PROVENANCE", path, "artifact and sha256 are required")
            return
        artifact, expected = raw.get("artifact"), raw.get("sha256")
        if not isinstance(artifact, str) or not artifact or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            self._error("CONTRACT.PROVENANCE", path, "artifact must be relative and sha256 must be lowercase hex")
            return
        try:
            target = _safe_child(root, artifact)
        except ValueError as error:
            self._error("CONTRACT.PROVENANCE", path, str(error))
            return
        if not target.is_file() or _sha256_file(target) != expected:
            self._error("CONTRACT.PROVENANCE", path, "artifact is missing or its SHA-256 differs")

    def _input_storage_id(
        self, op: Mapping[str, Any], name: str, tensor: Mapping[str, Any]
    ) -> str:
        source = tensor.get("source")
        if isinstance(source, Mapping) and source.get("type") == "operator":
            producer = source.get("operator_id")
            if isinstance(producer, str) and producer:
                return f"{producer}.output.D"
        if name == "B'" and op["type"] not in BP_INDEPENDENT_OPS:
            return f"{op['id']}.input.B"
        return f"{op['id']}.input.{name}"

    def _entry_for_key(self, root: Path, key: str) -> Any:
        for name in ("sca_cfg.json", "sca_cfg_D.json"):
            payload = self._load_json(root / name, "SCA.PARSE", f"$.{name}")
            if isinstance(payload, Mapping) and key in payload:
                return payload[key]
        return None

    @staticmethod
    def _peak_by_slice_bank(regions: list[MemoryRegion]) -> dict[str, int]:
        peaks: dict[str, int] = {}
        for region in regions:
            key = f"slice{region.slice_id:02d}.bank{region.bank}"
            peaks[key] = max(peaks.get(key, 0), region.end)
        return dict(sorted(peaks.items()))

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
        raise ValueError("boolean is not an integer literal")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.replace("_", "")
        try:
            return int(text, 0)
        except ValueError as error:
            raise ValueError(f"invalid integer literal {value!r}") from error
    raise ValueError(f"expected integer literal, got {type(value).__name__}")


def _positive_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("expected a positive integer")
    return value


def _shape(value: Any, params: Mapping[str, int]) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("shape must contain exactly three dimensions")
    dims = tuple(_shape_dim(item, params) for item in value)
    if any(item <= 0 for item in dims):
        raise ValueError("shape dimensions must be positive")
    return dims  # type: ignore[return-value]


def _shape_dim(value: Any, params: Mapping[str, int]) -> int:
    if isinstance(value, bool):
        raise ValueError("shape dimension cannot be boolean")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError("shape dimension must be integer or expression")
    node = ast.parse(value, mode="eval")

    def evaluate(item: ast.AST) -> int:
        if isinstance(item, ast.Expression):
            return evaluate(item.body)
        if isinstance(item, ast.Constant) and isinstance(item.value, int):
            return item.value
        if isinstance(item, ast.Name) and item.id in params:
            return params[item.id]
        if isinstance(item, ast.BinOp) and isinstance(item.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv)):
            left, right = evaluate(item.left), evaluate(item.right)
            if isinstance(item.op, ast.Add):
                return left + right
            if isinstance(item.op, ast.Sub):
                return left - right
            if isinstance(item.op, ast.Mult):
                return left * right
            if right == 0:
                raise ValueError("division by zero in shape expression")
            return left // right
        raise ValueError(f"unsupported shape expression {value!r}")

    return evaluate(node)


def _safe_child(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must remain relative to graph root")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes graph root") from error
    return resolved


def _binary_text_size(path: Path) -> int:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("binary text file is empty")
    widths = {len(line) for line in lines}
    if len(widths) != 1:
        raise ValueError("binary text lines have mixed widths")
    width = next(iter(widths))
    if width not in {32, 64, 128} or any(set(line) - {"0", "1"} for line in lines):
        raise ValueError("binary text must use uniform 32/64/128-bit lines")
    return len(lines) * width // 8


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
