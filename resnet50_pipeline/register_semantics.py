from __future__ import annotations

import ast
import csv
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_corpus import build_operator_config_corpus


SCHEMA = "ndpsim-register-semantics-contract-v1"
_CELL_REF = re.compile(r"([A-Z]+)(\d+)")
_WIDTH = re.compile(r"(\d+)\s*bit", re.IGNORECASE)
_RANGE = re.compile(r"\[(\d+)(?::(\d+))?\]")


class RegisterSemanticsError(ValueError):
    pass


def _column_number(name: str) -> int:
    value = 0
    for character in name:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(payload)
    strings: list[str] = []
    for item in root.findall("{*}si"):
        strings.append("".join(node.text or "" for node in item.findall(".//{*}t")))
    return strings


def read_xlsx_table(path: Path, *, sheet_name: str = "Register Map") -> list[list[Any]]:
    """Read a small xlsx table using only the Python standard library."""

    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise RegisterSemanticsError(f"cannot open workbook: {path}: {error}") from error
    with archive:
        shared = _xlsx_shared_strings(archive)
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("{*}Relationship")
        }
        target: str | None = None
        for sheet in workbook.findall(".//{*}sheet"):
            if sheet.attrib.get("name") != sheet_name:
                continue
            rel_id = next(
                (
                    value
                    for key, value in sheet.attrib.items()
                    if key.endswith("}id") or key == "r:id"
                ),
                None,
            )
            if rel_id is not None:
                target = rel_targets.get(rel_id)
            break
        if target is None:
            raise RegisterSemanticsError(f"worksheet is missing: {sheet_name}")
        target = target.replace("\\", "/").lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        worksheet = ElementTree.fromstring(archive.read(target))
        rows: dict[int, dict[int, Any]] = defaultdict(dict)
        max_column = 0
        for cell in worksheet.findall(".//{*}c"):
            reference = cell.attrib.get("r", "")
            match = _CELL_REF.fullmatch(reference)
            if match is None:
                continue
            column = _column_number(match.group(1))
            row = int(match.group(2))
            max_column = max(max_column, column)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("{*}v")
            if cell_type == "inlineStr":
                value: Any = "".join(
                    node.text or "" for node in cell.findall(".//{*}t")
                )
            elif value_node is None or value_node.text is None:
                value = None
            elif cell_type == "s":
                value = shared[int(value_node.text)]
            elif cell_type in {"str", "e"}:
                value = value_node.text
            else:
                raw = value_node.text
                try:
                    number = float(raw)
                    value = int(number) if number.is_integer() else number
                except ValueError:
                    value = raw
            rows[row][column] = value
        if not rows:
            return []
        return [
            [rows[row].get(column) for column in range(1, max_column + 1)]
            for row in range(1, max(rows) + 1)
        ]


def read_csv_table(path: Path) -> list[list[Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [list(row) for row in csv.reader(handle)]
    except (OSError, UnicodeError, csv.Error) as error:
        raise RegisterSemanticsError(f"cannot read register CSV: {path}: {error}") from error


def _field_width(field: Any) -> tuple[int | None, list[tuple[int, int]], int | None]:
    if not isinstance(field, str):
        return None, [], None
    width_match = _WIDTH.search(field)
    width = int(width_match.group(1)) if width_match else None
    ranges: list[tuple[int, int]] = []
    for high, low in _RANGE.findall(field):
        hi = int(high)
        lo = int(low) if low else hi
        ranges.append((hi, lo))
    span = sum(abs(high - low) + 1 for high, low in ranges) if ranges else None
    return width, ranges, span


def _normalized_tokens(value: str) -> list[str]:
    text = value.replace("sn2n", "n2n").replace("cfg_constant_pos", "constant")
    text = re.sub(r"\[\d+\]", "", text)
    tokens: list[str] = []
    for token in re.split(r"[.$\[\]]+", text):
        if not token:
            continue
        token = re.sub(r"^(stream|buffer|PE|LC)\d+$", r"\1", token)
        if token in {"stream", "buffer", "PE_array", "PE", "LC"}:
            continue
        tokens.append(token)
    return tokens


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    iterator = iter(haystack)
    return all(any(value == target for value in iterator) for target in needle)


def _match_config_name(
    config_name: str, normalized_json_paths: Iterable[str]
) -> tuple[str, list[str]]:
    if config_name == "config[use+update]":
        matches = [path for path in normalized_json_paths if path == "$.CONFIG"]
        return ("direct", matches)
    aliases = [config_name]
    if config_name == "general_array.inport.pingpong":
        aliases.append("general_array.inport.pingpong_en")
    direct_tokens = _normalized_tokens(config_name)
    direct = [
        path
        for path in normalized_json_paths
        if _is_subsequence(direct_tokens, _normalized_tokens(path))
    ]
    if direct:
        return "direct", direct
    for alias in aliases[1:]:
        alias_tokens = _normalized_tokens(alias)
        matches = [
            path
            for path in normalized_json_paths
            if _is_subsequence(alias_tokens, _normalized_tokens(path))
        ]
        if matches:
            return "alias", matches
    return "unmatched", []


def _encoder_field_maps(config_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(config_root.glob("*.py")):
        try:
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue
            assignments = [
                item
                for item in node.body
                if isinstance(item, (ast.Assign, ast.AnnAssign))
            ]
            for assignment in assignments:
                if isinstance(assignment, ast.Assign):
                    names = [
                        target.id
                        for target in assignment.targets
                        if isinstance(target, ast.Name)
                    ]
                    value = assignment.value
                else:
                    names = (
                        [assignment.target.id]
                        if isinstance(assignment.target, ast.Name)
                        else []
                    )
                    value = assignment.value
                if "FIELD_MAP" not in names or not isinstance(value, ast.List):
                    continue
                fields: list[dict[str, Any]] = []
                for element in value.elts:
                    if not isinstance(element, (ast.Tuple, ast.List)) or len(element.elts) < 2:
                        continue
                    try:
                        name = ast.literal_eval(element.elts[0])
                        width = ast.literal_eval(element.elts[1])
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    if isinstance(name, str) and isinstance(width, int):
                        fields.append({"name": name, "width": width})
                result[f"{path.name}:{node.name}"] = {
                    "path": path.as_posix(),
                    "class": node.name,
                    "fields": fields,
                    "total_width": sum(item["width"] for item in fields),
                }
    return result


def build_register_semantics_contract(
    project_root: Path,
    *,
    workbook_path: Path | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    if workbook_path is not None:
        source = workbook_path.resolve()
        table = read_xlsx_table(source)
        source_kind = "xlsx"
    else:
        source = (
            csv_path.resolve()
            if csv_path is not None
            else root / "ndp-sim/model_execplan/config/register_map_with_groups1.csv"
        )
        table = read_csv_table(source)
        source_kind = "csv"
    if not table or len(table[0]) < 4:
        raise RegisterSemanticsError("register table is empty or malformed")

    corpus = build_operator_config_corpus(root)
    normalized_json_paths = corpus["normalized_leaf_paths"]
    rows: list[dict[str, Any]] = []
    width_conflicts: list[dict[str, Any]] = []
    config_matches: list[dict[str, Any]] = []
    current_group: str | None = None
    current_module: str | None = None
    for row_index, values in enumerate(table[1:], start=2):
        padded = list(values) + [None] * max(0, 8 - len(values))
        group, module, field, config_name, note, port, port_note, default = padded[:8]
        if group not in (None, ""):
            current_group = str(group)
        if module not in (None, ""):
            current_module = str(module)
        width, ranges, span = _field_width(field)
        record = {
            "row": row_index,
            "group": current_group,
            "module": current_module,
            "field": field,
            "config_name": config_name,
            "note": note,
            "hardware_port": port,
            "hardware_note": port_note,
            "default": default,
            "declared_width": width,
            "bit_ranges": [[high, low] for high, low in ranges],
            "range_span": span,
        }
        rows.append(record)
        if width is not None and span is not None and width != span:
            width_conflicts.append(
                {
                    "row": row_index,
                    "group": current_group,
                    "module": current_module,
                    "field": field,
                    "declared_width": width,
                    "range_span": span,
                }
            )
        if row_index <= 134 and isinstance(config_name, str) and config_name:
            mode, matches = _match_config_name(config_name, normalized_json_paths)
            config_matches.append(
                {
                    "row": row_index,
                    "config_name": config_name,
                    "match_mode": mode,
                    "json_paths": matches,
                }
            )

    direct = sum(item["match_mode"] == "direct" for item in config_matches)
    aliases = sum(item["match_mode"] == "alias" for item in config_matches)
    unmatched = [item for item in config_matches if item["match_mode"] == "unmatched"]
    encoder_maps = _encoder_field_maps(root / "ndp-sim/bitstream/config")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "source": {
            "kind": source_kind,
            "name": source.name,
            "sha256": sha256_file(source),
            "size_bytes": source.stat().st_size,
            "sheet": "Register Map" if source_kind == "xlsx" else None,
        },
        "authority_policy": {
            "spreadsheet_role": "field names, hardware ports and semantic notes",
            "encoder_role": "current software packing implementation",
            "rtl_role": "final bit-level and runtime behavior authority",
            "width_or_offset_conflict_requires_arbitration": True,
        },
        "summary": {
            "table_row_count": len(table),
            "semantic_row_count": len(rows),
            "config_row_count": len(config_matches),
            "direct_json_match_count": direct,
            "alias_json_match_count": aliases,
            "unmatched_json_count": len(unmatched),
            "declared_width_range_conflict_count": len(width_conflicts),
            "encoder_field_map_count": len(encoder_maps),
        },
        "config_path_matches": config_matches,
        "declared_width_range_conflicts": width_conflicts,
        "rows": rows,
        "encoder_field_maps": encoder_maps,
        "unresolved_conflict_policy": {
            "do_not_copy_spreadsheet_bit_offsets_into_codegen": True,
            "require_encoder_and_rtl_cross_check": True,
            "examples": [
                "DRAM LC start/stride/end declared 17-bit but spreadsheet range spans 13 bits",
                "address_remapping declared 130-bit but spreadsheet range spans 64 bits",
                "write-stream tailing rows overlap earlier spreadsheet ranges",
                "several SA fields share spreadsheet bit 14",
            ],
        },
    }
    payload["contract_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_register_semantics_contract(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "RegisterSemanticsError",
    "build_register_semantics_contract",
    "read_csv_table",
    "read_xlsx_table",
    "write_register_semantics_contract",
]
