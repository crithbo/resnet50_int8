#!/usr/bin/env python3
"""Generate a source-bound, high-information server diagnostic observer.

The family owner selects immutable ``symbol_id`` values from a catalog created
from the pinned RTL sources.  The final SystemVerilog, logger format, parser,
binding manifest and cheap prebuild receipt are then generated together.  No
free-form HDL identifier or hierarchy expression is accepted by the plan.

This tool only materializes package-local diagnostic sources.  It does not
build a server ZIP, modify RTL, run a simulator, or change package release
state.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
ROLE_SET = {
    "source_produce",
    "queue_enqueue",
    "queue_dequeue",
    "consumer_accept",
    "internal_match_compute",
    "output_accept",
    "terminal_propagation",
    "formal_d_collection",
}
OBSERVATION_METRICS = {"summary_present", "count_nonzero", "class_seen"}
PLAN_SCHEMAS = {
    "server-source-bound-probe-plan-v1",
    "server-source-bound-probe-plan-v2",
}
INSTANCE_SCOPE_MODES = {
    "EXACT_CANONICAL_INSTANCE",
    "EXACT_CANONICAL_INSTANCE_SET",
    "ALL_INSTANCES_KEYED",
}
PAYLOAD_RECORD_KINDS = {"EVENT", "TRIGGER", "RING_PROGRESS", "RING_POST"}


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_json_bytes(value))


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode(
            "utf-8"
        )
        + b"\n"
    )


def file_receipt(path: Path, root: Path | None = None) -> dict[str, Any]:
    resolved = path.resolve()
    label = resolved.as_posix()
    if root is not None:
        try:
            label = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _strip_comments_preserve_lines(text: str) -> str:
    def block(match: re.Match[str]) -> str:
        value = match.group(0)
        return "".join("\n" if character == "\n" else " " for character in value)

    text = re.sub(r"/\*.*?\*/", block, text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", lambda match: " " * len(match.group(0)), text)


def _literal_integer(expression: str, macros: dict[str, int]) -> int | None:
    replaced = re.sub(
        r"`([A-Za-z_][A-Za-z0-9_$]*)",
        lambda match: str(macros.get(match.group(1), match.group(0))),
        expression,
    )
    if "`" in replaced:
        return None
    while True:
        clog2 = re.search(r"\$clog2\(([^()]+)\)", replaced)
        if clog2 is None:
            break
        argument = _literal_integer(clog2.group(1), macros)
        if argument is None or argument <= 0:
            return None
        replaced = (
            replaced[: clog2.start()]
            + str((argument - 1).bit_length())
            + replaced[clog2.end() :]
        )
    if "$" in replaced:
        return None
    try:
        tree = ast.parse(replaced, mode="eval")
    except SyntaxError:
        return None

    def evaluate(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Div)
        ):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ValueError("division by zero")
            return left // right
        raise ValueError("unsupported literal expression")

    try:
        return evaluate(tree)
    except ValueError:
        return None


def _literal_width(
    range_text: str | None, macros: dict[str, int] | None = None
) -> tuple[int | None, str]:
    if not range_text:
        return 1, "1"
    expression = range_text.strip()[1:-1].strip()
    match = re.fullmatch(r"(.+?)\s*:\s*(.+)", expression)
    if not match:
        return None, expression
    macros = macros or {}
    left = _literal_integer(match.group(1), macros)
    right = _literal_integer(match.group(2), macros)
    if left is None or right is None:
        return None, expression
    return abs(left - right) + 1, expression


def _symbol_id(
    rtl_tree_sha256: str,
    relative: str,
    module: str,
    name: str,
    declaration_sha256: str,
) -> str:
    value = {
        "rtl_tree_sha256": rtl_tree_sha256,
        "path": relative,
        "module": module,
        "name": name,
        "declaration_sha256": declaration_sha256,
    }
    return "sym_" + semantic_sha256(value)[:24]


def _extract_declared_names(value: str) -> list[str]:
    names: list[str] = []
    for item in value.split(","):
        item = item.split("=")[0].strip()
        item = re.sub(r"\[[^\]]+\]\s*$", "", item).strip()
        match = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)", item)
        if match:
            names.append(match.group(1))
    return names


def _matching_paren(text: str, start: int) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_top_level_commas(text: str) -> list[tuple[int, str]]:
    depth = 0
    start = 0
    values: list[tuple[int, str]] = []
    for index, character in enumerate(text):
        if character in "([{" :
            depth += 1
        elif character in ")]}":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            values.append((start, text[start:index]))
            start = index + 1
    values.append((start, text[start:]))
    return values


def _extract_symbols(
    text: str,
    relative: str,
    source_sha256: str,
    rtl_tree_sha256: str,
    macros: dict[str, int] | None = None,
    allow_empty: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    cleaned = _strip_comments_preserve_lines(text)
    symbols: list[dict[str, Any]] = []
    errors: list[str] = []
    module_pattern = re.compile(
        r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b(?P<body>.*?)\bendmodule\b",
        re.DOTALL,
    )
    for module_match in module_pattern.finditer(cleaned):
        module = module_match.group(1)
        body = module_match.group("body")
        body_start = module_match.start("body")
        declarations: list[tuple[int, int, str, str | None, str, str]] = []

        cursor = 0
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor < len(body) and body[cursor] == "#":
            parameter_open = body.find("(", cursor)
            parameter_close = (
                _matching_paren(body, parameter_open)
                if parameter_open >= 0
                else None
            )
            if parameter_close is not None:
                cursor = parameter_close + 1
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor < len(body) and body[cursor] == "(":
            port_close = _matching_paren(body, cursor)
            if port_close is not None:
                port_text = body[cursor + 1 : port_close]
                current_kind: str | None = None
                current_range: str | None = None
                for relative_start, raw_item in _split_top_level_commas(port_text):
                    item = raw_item.strip()
                    if not item:
                        continue
                    explicit = re.match(
                        r"(input|output|inout)\s+"
                        r"(?:(?:wire|logic|reg)\s+)?(?:signed\s+)?"
                        r"(\[[^\]]+\]\s*)?(.*)$",
                        item,
                    )
                    if explicit:
                        current_kind = explicit.group(1)
                        current_range = explicit.group(2)
                        names_text = explicit.group(3)
                    else:
                        names_text = item
                    if current_kind is None:
                        continue
                    for name in _extract_declared_names(names_text):
                        name_offset = raw_item.find(name)
                        absolute = body_start + cursor + 1 + relative_start + max(0, name_offset)
                        declarations.append(
                            (
                                absolute,
                                absolute + len(name),
                                current_kind,
                                current_range,
                                name,
                                item,
                            )
                        )

        port_pattern = re.compile(
            r"(?:^|[(,;])\s*(input|output|inout)\s+"
            r"(?:(wire|logic|reg)\s+)?(?:signed\s+)?"
            r"(\[[^\]]+\]\s*)?([A-Za-z_][A-Za-z0-9_$]*)",
            re.MULTILINE,
        )
        for match in port_pattern.finditer(body):
            declarations.append(
                (
                    body_start + match.start(4),
                    body_start + match.end(4),
                    match.group(1),
                    match.group(3),
                    match.group(4),
                    match.group(0).lstrip("(,; "),
                )
            )

        internal_pattern = re.compile(
            r"(?m)^\s*(wire|logic|reg)\s+(?:signed\s+)?"
            r"(\[[^\]]+\]\s*)?([^;]+);"
        )
        for match in internal_pattern.finditer(body):
            for name in _extract_declared_names(match.group(3)):
                name_match = re.search(rf"\b{re.escape(name)}\b", match.group(0))
                if not name_match:
                    continue
                declarations.append(
                    (
                        body_start + match.start() + name_match.start(),
                        body_start + match.start() + name_match.end(),
                        match.group(1),
                        match.group(2),
                        name,
                        match.group(0).strip(),
                    )
                )

        seen: set[str] = set()
        for start, end, kind, range_text, name, declaration in sorted(declarations):
            if name in seen:
                continue
            seen.add(name)
            line = cleaned.count("\n", 0, start) + 1
            width_bits, width_expression = _literal_width(range_text, macros)
            declaration_sha = sha256_bytes(declaration.encode("utf-8"))
            symbols.append(
                {
                    "symbol_id": _symbol_id(
                        rtl_tree_sha256,
                        relative,
                        module,
                        name,
                        declaration_sha,
                    ),
                    "module": module,
                    "name": name,
                    "declaration_kind": kind,
                    "width_bits": width_bits,
                    "width_expression": width_expression,
                    "source": {
                        "path": relative,
                        "source_sha256": source_sha256,
                        "line": line,
                        "source_span": f"{line}:{start}-{end}",
                        "declaration_sha256": declaration_sha,
                    },
                }
            )
    if not symbols and not allow_empty:
        errors.append(f"no module signal declarations discovered: {relative}")
    return symbols, errors


def build_catalog(
    rtl_root: Path,
    source_paths: Iterable[Path],
    rtl_tree_sha256: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if not HEX64.fullmatch(rtl_tree_sha256):
        errors.append("rtl_tree_sha256 is invalid")
    receipts: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    root = rtl_root.resolve()
    decoded_sources: list[tuple[str, str, str, bool]] = []
    for supplied in source_paths:
        path = supplied.resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"RTL source escapes rtl_root: {supplied}")
            continue
        if not path.is_file():
            errors.append(f"RTL source is missing: {relative}")
            continue
        data = path.read_bytes()
        source_sha = sha256_bytes(data)
        receipts.append({"path": relative, "bytes": len(data), "sha256": source_sha})
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"RTL source is not UTF-8: {relative}: {exc}")
            continue
        decoded_sources.append((relative, text, source_sha, path.suffix.lower() == ".svh"))
    macros: dict[str, int] = {}
    raw_macros: dict[str, str] = {}
    for _, text, _, _ in decoded_sources:
        for match in re.finditer(
            r"(?m)^\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)\s+([^\s/]+)", text
        ):
            raw_macros[match.group(1)] = match.group(2)
    for _ in range(len(raw_macros) + 1):
        changed = False
        for name, expression in raw_macros.items():
            value = _literal_integer(expression, macros)
            if value is not None and macros.get(name) != value:
                macros[name] = value
                changed = True
        if not changed:
            break
    for relative, text, source_sha, allow_empty in decoded_sources:
        extracted, source_errors = _extract_symbols(
            text,
            relative,
            source_sha,
            rtl_tree_sha256,
            macros=macros,
            allow_empty=allow_empty,
        )
        symbols.extend(extracted)
        errors.extend(source_errors)
    ids = [item["symbol_id"] for item in symbols]
    duplicate_ids = sorted(key for key, value in Counter(ids).items() if value > 1)
    if duplicate_ids:
        errors.append(f"duplicate symbol ids: {duplicate_ids}")
    module_sources: dict[str, set[str]] = {}
    for item in symbols:
        module_sources.setdefault(item["module"], set()).add(item["source"]["path"])
    duplicate_modules = {
        module: sorted(paths)
        for module, paths in module_sources.items()
        if len(paths) > 1
    }
    if duplicate_modules:
        errors.append(f"module definitions span multiple sources: {duplicate_modules}")
    module_names = sorted({item["module"] for item in symbols})
    report = {
        "schema": "server-source-bound-probe-catalog-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "rtl_identity": {
            "rtl_root_label": rtl_root.name,
            "rtl_tree_sha256": rtl_tree_sha256,
            "sources": sorted(receipts, key=lambda item: item["path"]),
        },
        "module_count": len(module_names),
        "modules": module_names,
        "symbol_count": len(symbols),
        "symbols": sorted(symbols, key=lambda item: (item["module"], item["name"])),
        "errors": errors,
        "valid": not errors,
        "claim_boundary": (
            "Source declaration inventory only; no hierarchy guess, RTL change, "
            "simulation, package build, or functional claim."
        ),
    }
    return report


def _predicate_symbol_ids(predicate: Any, errors: list[str], label: str) -> set[str]:
    found: set[str] = set()
    if not isinstance(predicate, dict):
        errors.append(f"{label}: predicate must be an object")
        return found
    op = predicate.get("op")
    if op == "SIGNAL":
        value = predicate.get("symbol_id")
        if not isinstance(value, str):
            errors.append(f"{label}: SIGNAL symbol_id is missing")
        else:
            found.add(value)
    elif op == "BIT_AND_NONZERO":
        values = predicate.get("symbol_ids")
        if (
            not isinstance(values, list)
            or len(values) != 2
            or not all(isinstance(value, str) for value in values)
        ):
            errors.append(
                f"{label}: BIT_AND_NONZERO symbol_ids must contain exactly two symbol ids"
            )
        else:
            found.update(values)
    elif op in {"EQ", "NE"}:
        value = predicate.get("symbol_id")
        literal = predicate.get("value")
        if not isinstance(value, str):
            errors.append(f"{label}: {op} symbol_id is missing")
        else:
            found.add(value)
        if not isinstance(literal, int) or literal < 0:
            errors.append(f"{label}: {op} value must be a nonnegative integer")
    elif op == "NOT":
        found |= _predicate_symbol_ids(predicate.get("arg"), errors, f"{label}.arg")
    elif op in {"AND", "OR"}:
        args = predicate.get("args")
        if not isinstance(args, list) or not args:
            errors.append(f"{label}: {op} args must be a nonempty array")
        else:
            for index, item in enumerate(args):
                found |= _predicate_symbol_ids(item, errors, f"{label}.args[{index}]")
    elif op == "CONST":
        if predicate.get("value") not in {0, 1, False, True}:
            errors.append(f"{label}: CONST value must be boolean")
    else:
        errors.append(f"{label}: unsupported predicate op: {op}")
    return found


def _validate_predicate_semantics(
    predicate: Any,
    symbols: dict[str, dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    if not isinstance(predicate, dict):
        return
    op = predicate.get("op")
    if op == "BIT_AND_NONZERO":
        values = predicate.get("symbol_ids")
        if isinstance(values, list) and len(values) == 2:
            widths = [
                symbols.get(value, {}).get("width_bits")
                for value in values
                if isinstance(value, str)
            ]
            if len(widths) == 2 and all(isinstance(width, int) for width in widths):
                if widths[0] != widths[1]:
                    errors.append(
                        f"{label}: BIT_AND_NONZERO operands must have equal widths"
                    )
    elif op == "NOT":
        _validate_predicate_semantics(predicate.get("arg"), symbols, errors, f"{label}.arg")
    elif op in {"AND", "OR"}:
        for index, item in enumerate(predicate.get("args", [])):
            _validate_predicate_semantics(item, symbols, errors, f"{label}.args[{index}]")


def _predicate_sv(predicate: dict[str, Any], aliases: dict[str, str]) -> str:
    op = predicate["op"]
    if op == "SIGNAL":
        return f"({aliases[predicate['symbol_id']]} === 1'b1)"
    if op == "BIT_AND_NONZERO":
        left, right = predicate["symbol_ids"]
        return f"((|({aliases[left]} & {aliases[right]})) === 1'b1)"
    if op == "EQ":
        return f"({aliases[predicate['symbol_id']]} == {int(predicate['value'])})"
    if op == "NE":
        return f"({aliases[predicate['symbol_id']]} != {int(predicate['value'])})"
    if op == "NOT":
        return f"!({_predicate_sv(predicate['arg'], aliases)})"
    if op in {"AND", "OR"}:
        joiner = " && " if op == "AND" else " || "
        return "(" + joiner.join(_predicate_sv(item, aliases) for item in predicate["args"]) + ")"
    return "1'b1" if predicate["value"] else "1'b0"


def _safe_identifier(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_$]", "_", value)
    if not safe or safe[0].isdigit():
        safe = "p_" + safe
    return safe


def validate_contract(catalog: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if catalog.get("schema") != "server-source-bound-probe-catalog-v1":
        errors.append("catalog schema mismatch")
    if catalog.get("valid") is not True:
        errors.append("catalog is not valid")
    plan_schema = plan.get("schema")
    if plan_schema not in PLAN_SCHEMAS:
        errors.append("plan schema mismatch")
    strict_semantics = plan_schema == "server-source-bound-probe-plan-v2"
    diagnostic_semantics = plan.get("diagnostic_semantics")
    if strict_semantics:
        expected_policies = {
            "instance_match": "EXACT_CANONICAL_EQUALITY",
            "record_grouping_key": ["boundary_id", "canonical_instance", "seq"],
            "unknown_payload": "EVIDENCE_INCOMPLETE",
            "numeric_parse_failure": "EVIDENCE_INCOMPLETE",
            "candidate_match_cardinality": "EXACTLY_ONE",
        }
        if not isinstance(diagnostic_semantics, dict):
            errors.append("diagnostic_semantics is required for plan v2")
            diagnostic_semantics = {}
        for field, expected in expected_policies.items():
            if diagnostic_semantics.get(field) != expected:
                errors.append(
                    f"diagnostic_semantics.{field} must equal {expected!r}"
                )
    if plan.get("profile") != "HIGH_INFORMATION_CAUSAL_V1":
        errors.append("plan profile must be HIGH_INFORMATION_CAUSAL_V1")
    for field in ("package_id", "family"):
        if not isinstance(plan.get(field), str) or not plan[field]:
            errors.append(f"{field} must be a nonempty string")
    if plan.get("catalog_identity", {}).get("rtl_tree_sha256") != catalog.get("rtl_identity", {}).get("rtl_tree_sha256"):
        errors.append("plan/catalog RTL tree SHA mismatch")
    expected_catalog_semantic = semantic_sha256(catalog)
    if plan.get("catalog_identity", {}).get("catalog_semantic_sha256") != expected_catalog_semantic:
        errors.append("plan/catalog semantic SHA mismatch")

    symbols = {
        item.get("symbol_id"): item
        for item in catalog.get("symbols", [])
        if isinstance(item, dict) and isinstance(item.get("symbol_id"), str)
    }
    boundaries = plan.get("boundaries")
    if not isinstance(boundaries, list) or not boundaries:
        errors.append("boundaries must be a nonempty array")
        boundaries = []
    boundary_ids = [item.get("boundary_id") for item in boundaries if isinstance(item, dict)]
    duplicates = sorted(key for key, value in Counter(boundary_ids).items() if key and value > 1)
    if duplicates:
        errors.append(f"duplicate boundary ids: {duplicates}")
    boundary_map: dict[str, dict[str, Any]] = {}
    bound_symbol_ids: set[str] = set()
    for index, boundary in enumerate(boundaries):
        label = f"boundaries[{index}]"
        if not isinstance(boundary, dict):
            errors.append(f"{label} must be an object")
            continue
        boundary_id = boundary.get("boundary_id")
        if not isinstance(boundary_id, str) or not boundary_id:
            errors.append(f"{label}.boundary_id is invalid")
            continue
        boundary_map[boundary_id] = boundary
        if boundary.get("role") not in ROLE_SET:
            errors.append(f"{label}.role is invalid: {boundary.get('role')}")
        module = boundary.get("target_module")
        if not isinstance(module, str) or not IDENT.fullmatch(module):
            errors.append(f"{label}.target_module is invalid")
            module = ""
        instance_scope = boundary.get("instance_scope")
        if strict_semantics:
            if not isinstance(instance_scope, dict):
                errors.append(f"{label}.instance_scope is required for plan v2")
                instance_scope = {}
            mode = instance_scope.get("mode")
            if mode not in INSTANCE_SCOPE_MODES:
                errors.append(f"{label}.instance_scope.mode is invalid")
            expected_instances = instance_scope.get("expected_instances", [])
            near_miss_instances = instance_scope.get("near_miss_instances", [])
            if not isinstance(expected_instances, list) or not all(
                isinstance(item, str) and item for item in expected_instances
            ):
                errors.append(
                    f"{label}.instance_scope.expected_instances must be strings"
                )
                expected_instances = []
            if not isinstance(near_miss_instances, list) or not all(
                isinstance(item, str) and item for item in near_miss_instances
            ):
                errors.append(
                    f"{label}.instance_scope.near_miss_instances must be strings"
                )
                near_miss_instances = []
            if len(expected_instances) != len(set(expected_instances)):
                errors.append(f"{label}.instance_scope has duplicate expected instances")
            if len(near_miss_instances) != len(set(near_miss_instances)):
                errors.append(f"{label}.instance_scope has duplicate near-miss instances")
            if set(expected_instances) & set(near_miss_instances):
                errors.append(f"{label}.instance_scope expected/near-miss overlap")
            if mode == "EXACT_CANONICAL_INSTANCE" and len(expected_instances) != 1:
                errors.append(
                    f"{label}.instance_scope exact mode requires one expected instance"
                )
            if mode == "EXACT_CANONICAL_INSTANCE_SET" and not expected_instances:
                errors.append(
                    f"{label}.instance_scope exact-set mode requires expected instances"
                )
            if mode in {"EXACT_CANONICAL_INSTANCE", "EXACT_CANONICAL_INSTANCE_SET"}:
                if not near_miss_instances:
                    errors.append(
                        f"{label}.instance_scope requires a near-miss negative instance"
                    )
                provenance = instance_scope.get("identity_provenance")
                if not isinstance(provenance, dict):
                    errors.append(
                        f"{label}.instance_scope.identity_provenance is required"
                    )
                else:
                    if not isinstance(provenance.get("path"), str) or not provenance.get("path"):
                        errors.append(f"{label}.instance_scope provenance path is invalid")
                    if not HEX64.fullmatch(str(provenance.get("sha256", ""))):
                        errors.append(f"{label}.instance_scope provenance SHA is invalid")
                    if not isinstance(provenance.get("selector"), str) or not provenance.get("selector"):
                        errors.append(f"{label}.instance_scope provenance selector is invalid")
        local_ids: set[str] = set()
        for field in ("clock_symbol_id",):
            value = boundary.get(field)
            if not isinstance(value, str):
                errors.append(f"{label}.{field} is missing")
            else:
                local_ids.add(value)
        reset = boundary.get("reset")
        if not isinstance(reset, dict) or not isinstance(reset.get("symbol_id"), str):
            errors.append(f"{label}.reset is invalid")
        else:
            local_ids.add(reset["symbol_id"])
            if not isinstance(reset.get("active_low"), bool):
                errors.append(f"{label}.reset.active_low must be boolean")
        classes = boundary.get("classes")
        if not isinstance(classes, list) or not classes:
            errors.append(f"{label}.classes must be nonempty")
            classes = []
        class_ids: list[str] = []
        class_bits: list[int] = []
        progress_count = 0
        for class_index, class_spec in enumerate(classes):
            class_label = f"{label}.classes[{class_index}]"
            if not isinstance(class_spec, dict):
                errors.append(f"{class_label} must be an object")
                continue
            class_id = class_spec.get("class_id")
            bit = class_spec.get("bit")
            if not isinstance(class_id, str) or not class_id:
                errors.append(f"{class_label}.class_id is invalid")
            else:
                class_ids.append(class_id)
            if not isinstance(bit, int) or not 0 <= bit <= 31:
                errors.append(f"{class_label}.bit must be 0..31")
            else:
                class_bits.append(bit)
            if class_spec.get("progress") is True:
                progress_count += 1
            elif class_spec.get("progress") is not False:
                errors.append(f"{class_label}.progress must be boolean")
            if not isinstance(class_spec.get("trigger"), bool):
                errors.append(f"{class_label}.trigger must be boolean")
            local_ids |= _predicate_symbol_ids(class_spec.get("predicate"), errors, f"{class_label}.predicate")
            _validate_predicate_semantics(
                class_spec.get("predicate"), symbols, errors, f"{class_label}.predicate"
            )
        if len(class_ids) != len(set(class_ids)):
            errors.append(f"{label}: duplicate class ids")
        if len(class_bits) != len(set(class_bits)):
            errors.append(f"{label}: duplicate class bits")
        if progress_count == 0:
            warnings.append(f"{boundary_id}: no progress class; no-progress reset is intentionally disabled")
        gate = boundary.get("stage_gate", {"op": "CONST", "value": 1})
        local_ids |= _predicate_symbol_ids(gate, errors, f"{label}.stage_gate")
        _validate_predicate_semantics(gate, symbols, errors, f"{label}.stage_gate")
        payload_ids = boundary.get("payload_symbol_ids", [])
        if not isinstance(payload_ids, list) or not all(isinstance(item, str) for item in payload_ids):
            errors.append(f"{label}.payload_symbol_ids must be an array of symbol ids")
            payload_ids = []
        local_ids.update(payload_ids)
        for symbol_id in sorted(local_ids):
            symbol = symbols.get(symbol_id)
            if symbol is None:
                errors.append(f"{label}: unresolved symbol_id: {symbol_id}")
                continue
            if symbol.get("module") != module:
                errors.append(
                    f"{label}: symbol {symbol_id} belongs to {symbol.get('module')} not {module}"
                )
        for field_id, field_name in (
            (boundary.get("clock_symbol_id"), "clock"),
            ((reset or {}).get("symbol_id") if isinstance(reset, dict) else None, "reset"),
        ):
            symbol = symbols.get(field_id)
            if symbol is not None and symbol.get("width_bits") != 1:
                errors.append(f"{label}: {field_name} symbol must be one bit")
        payload_width = 0
        for symbol_id in payload_ids:
            symbol = symbols.get(symbol_id)
            if symbol is None:
                continue
            width = symbol.get("width_bits")
            if not isinstance(width, int):
                errors.append(f"{label}: payload width is not literal for {symbol_id}")
            else:
                payload_width += width
        if payload_width > 1024:
            errors.append(f"{label}: payload concat exceeds 1024 bits")
        if strict_semantics:
            payload_contract = boundary.get("payload_contract")
            if not isinstance(payload_contract, dict):
                errors.append(f"{label}.payload_contract is required for plan v2")
            else:
                if payload_contract.get("width_bits") != payload_width:
                    errors.append(
                        f"{label}.payload_contract.width_bits must equal {payload_width}"
                    )
                if payload_contract.get("required_binary_known") is not True:
                    errors.append(
                        f"{label}.payload_contract.required_binary_known must be true"
                    )
                if payload_contract.get("unknown_disposition") != "EVIDENCE_INCOMPLETE":
                    errors.append(
                        f"{label}.payload_contract.unknown_disposition must be EVIDENCE_INCOMPLETE"
                    )
        bound_symbol_ids |= local_ids

    role_coverage = plan.get("role_coverage")
    if not isinstance(role_coverage, list):
        errors.append("role_coverage must be an array")
        role_coverage = []
    coverage_by_role: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(role_coverage):
        if not isinstance(item, dict) or item.get("role") not in ROLE_SET:
            errors.append(f"role_coverage[{index}] is invalid")
            continue
        role = item["role"]
        if role in coverage_by_role:
            errors.append(f"duplicate role coverage: {role}")
        coverage_by_role[role] = item
        disposition = item.get("disposition")
        ids = item.get("boundary_ids", [])
        if disposition == "covered":
            if not isinstance(ids, list) or not ids:
                errors.append(f"role {role} covered without boundary_ids")
            else:
                for boundary_id in ids:
                    if boundary_id not in boundary_map:
                        errors.append(f"role {role} references unknown boundary {boundary_id}")
                    elif boundary_map[boundary_id].get("role") != role:
                        errors.append(f"role {role} references mismatched boundary {boundary_id}")
        elif disposition == "not_applicable":
            if ids:
                errors.append(f"role {role} not_applicable must not list boundaries")
            if not isinstance(item.get("reason"), str) or not item["reason"]:
                errors.append(f"role {role} not_applicable lacks reason")
        else:
            errors.append(f"role {role} has invalid disposition")
    missing_roles = sorted(ROLE_SET - set(coverage_by_role))
    if missing_roles:
        errors.append(f"role coverage is incomplete: {missing_roles}")

    observations = plan.get("decision_observations")
    if not isinstance(observations, list) or not observations:
        errors.append("decision_observations must be nonempty")
        observations = []
    observation_ids: list[str] = []
    observation_map: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(observations):
        label = f"decision_observations[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        observation_id = item.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id:
            errors.append(f"{label}.observation_id is invalid")
            continue
        observation_ids.append(observation_id)
        observation_map[observation_id] = item
        boundary_id = item.get("boundary_id")
        metric = item.get("metric")
        if boundary_id not in boundary_map:
            errors.append(f"{label} references unknown boundary: {boundary_id}")
        if metric not in OBSERVATION_METRICS:
            errors.append(f"{label}.metric is invalid: {metric}")
        if metric == "class_seen":
            classes = boundary_map.get(boundary_id, {}).get("classes", [])
            available = {entry.get("class_id") for entry in classes if isinstance(entry, dict)}
            if item.get("class_id") not in available:
                errors.append(f"{label}.class_id is not bound at {boundary_id}")
        if strict_semantics and boundary_id in boundary_map:
            scope = boundary_map[boundary_id].get("instance_scope", {})
            if scope.get("mode") == "ALL_INSTANCES_KEYED":
                errors.append(
                    f"{label}: decision observations require a pinned exact instance scope"
                )
    duplicate_observations = sorted(key for key, value in Counter(observation_ids).items() if value > 1)
    if duplicate_observations:
        errors.append(f"duplicate observation ids: {duplicate_observations}")

    candidates = plan.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must be nonempty")
        candidates = []
    candidate_ids: list[str] = []
    signatures: dict[tuple[tuple[str, bool], ...], list[str]] = {}
    indistinguishable_pairs: list[list[str]] = []
    for index, candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be an object")
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{label}.candidate_id is invalid")
            continue
        candidate_ids.append(candidate_id)
        signature = candidate.get("signature")
        if not isinstance(signature, dict):
            errors.append(f"{label}.signature must be an object")
            continue
        missing = sorted(set(observation_ids) - set(signature))
        extra = sorted(set(signature) - set(observation_ids))
        if missing:
            errors.append(f"{label}.signature missing observations: {missing}")
        if extra:
            errors.append(f"{label}.signature has unknown observations: {extra}")
        invalid = sorted(key for key, value in signature.items() if not isinstance(value, bool))
        if invalid:
            errors.append(f"{label}.signature values must be boolean: {invalid}")
        normalized = tuple(sorted((key, value) for key, value in signature.items() if isinstance(value, bool)))
        signatures.setdefault(normalized, []).append(candidate_id)
        if not isinstance(candidate.get("root_cause_class"), str) or not candidate["root_cause_class"]:
            errors.append(f"{label}.root_cause_class is invalid")
    duplicate_candidates = sorted(key for key, value in Counter(candidate_ids).items() if value > 1)
    if duplicate_candidates:
        errors.append(f"duplicate candidate ids: {duplicate_candidates}")
    for values in signatures.values():
        if len(values) > 1:
            for left_index in range(len(values)):
                for right_index in range(left_index + 1, len(values)):
                    indistinguishable_pairs.append([values[left_index], values[right_index]])
    if indistinguishable_pairs:
        errors.append(f"candidate signatures are not unique: {indistinguishable_pairs}")
    if strict_semantics and not any(
        isinstance(candidate, dict)
        and isinstance(candidate.get("signature"), dict)
        and any(
            observation.get("metric") == "count_nonzero"
            and candidate["signature"].get(observation.get("observation_id")) is True
            for observation in observations
            if isinstance(observation, dict)
        )
        for candidate in candidates
    ):
        errors.append(
            "plan v2 requires a payload-bearing positive candidate control"
        )

    budget = plan.get("runtime_budget")
    if not isinstance(budget, dict):
        errors.append("runtime_budget must be an object")
        budget = {}
    for field, low, high in (
        ("qualified_ring_depth", 1, 4096),
        ("non_progress_ring_depth", 1, 4096),
        ("first_payload_samples", 1, 64),
        ("post_trigger_samples", 0, 1024),
        ("no_progress_cycles", 1, 10**12),
        ("max_log_bytes", 1024, 64 * 1024 * 1024),
    ):
        value = budget.get(field)
        if not isinstance(value, int) or not low <= value <= high:
            errors.append(f"runtime_budget.{field} must be {low}..{high}")
    if budget.get("state_activity_consumes_qualified_budget") is not False:
        errors.append("state activity must not consume qualified budget")
    if budget.get("multiclass_encoding") != "BITMAP_ALL_TRUE_CLASSES":
        errors.append("multiclass encoding must preserve all true classes")
    if budget.get("text_io_policy") != "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY":
        errors.append("text I/O policy must be bounded and trigger/final only")

    report = {
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
        "catalog_semantic_sha256": expected_catalog_semantic,
        "bound_symbol_count": len(bound_symbol_ids),
        "boundary_count": len(boundary_map),
        "strict_diagnostic_semantics": strict_semantics,
        "instance_scoped_boundary_count": sum(
            isinstance(item, dict) and isinstance(item.get("instance_scope"), dict)
            for item in boundaries
        ),
        "candidate_count": len(candidate_ids),
        "observation_count": len(observation_ids),
        "indistinguishable_candidate_pairs": indistinguishable_pairs,
    }
    return report


def _boundary_symbols(boundary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    values: set[str] = {boundary["clock_symbol_id"], boundary["reset"]["symbol_id"]}
    values |= _predicate_symbol_ids(boundary.get("stage_gate", {"op": "CONST", "value": 1}), errors, "stage_gate")
    for item in boundary["classes"]:
        values |= _predicate_symbol_ids(item["predicate"], errors, "class")
    values |= set(boundary.get("payload_symbol_ids", []))
    return sorted(values)


def generate_observer(catalog: dict[str, Any], plan: dict[str, Any]) -> str:
    symbols = {item["symbol_id"]: item for item in catalog["symbols"]}
    budget = plan["runtime_budget"]
    plan_sha = semantic_sha256(plan)
    catalog_sha = semantic_sha256(catalog)
    chunks = [
        "// Generated by generate_server_source_bound_observer.py; do not hand edit.",
        f"// catalog_semantic_sha256={catalog_sha}",
        f"// plan_semantic_sha256={plan_sha}",
        "`timescale 1ns/1ps",
        "",
    ]
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        safe = _safe_identifier(boundary_id)
        module_name = f"codex_probe_{safe}"
        symbol_ids = _boundary_symbols(boundary)
        aliases = {symbol_id: f"p_{index}" for index, symbol_id in enumerate(symbol_ids)}
        ports: list[str] = []
        for symbol_id in symbol_ids:
            symbol = symbols[symbol_id]
            width = symbol.get("width_bits")
            width_decl = "" if width == 1 else f"[{width - 1}:0] "
            ports.append(f"    input wire {width_decl}{aliases[symbol_id]}")
        classes = sorted(boundary["classes"], key=lambda item: item["bit"])
        mask_width = max(item["bit"] for item in classes) + 1
        progress_exprs = [
            _predicate_sv(item["predicate"], aliases)
            for item in classes
            if item["progress"]
        ]
        class_by_bit = {item["bit"]: item for item in classes}
        mask_expressions = [
            _predicate_sv(class_by_bit[bit]["predicate"], aliases)
            if bit in class_by_bit
            else "1'b0"
            for bit in reversed(range(mask_width))
        ]
        class_counter_updates = []
        for item in classes:
            condition = _predicate_sv(item["predicate"], aliases)
            if item["progress"]:
                class_counter_updates.append(
                    f"if ({condition}) codex_class_count[{item['bit']}] <= codex_class_count[{item['bit']}] + 1;"
                )
            else:
                class_counter_updates.append(
                    f"if (class_mask_now[{item['bit']}] != codex_prev_state_mask[{item['bit']}]) codex_class_count[{item['bit']}] <= codex_class_count[{item['bit']}] + 1;"
                )
        class_final_lines = [
            f"$display(\"CODEX_PROBE_V1 kind=CLASS boundary={boundary_id} instance=%m class={item['class_id']} count=%0d seen=%0d progress={1 if item['progress'] else 0}\", codex_class_count[{item['bit']}], codex_sticky_mask[{item['bit']}]);"
            for item in classes
        ]
        gate_expr = _predicate_sv(boundary.get("stage_gate", {"op": "CONST", "value": 1}), aliases)
        payload_ids = boundary.get("payload_symbol_ids", [])
        payload_width = sum(symbols[item]["width_bits"] for item in payload_ids) if payload_ids else 1
        payload_expr = "{" + ", ".join(aliases[item] for item in payload_ids) + "}" if payload_ids else "1'b0"
        reset_alias = aliases[boundary["reset"]["symbol_id"]]
        reset_ok = reset_alias if boundary["reset"]["active_low"] else f"!{reset_alias}"
        clock_alias = aliases[boundary["clock_symbol_id"]]
        progress_expr = " || ".join(progress_exprs) if progress_exprs else "1'b0"
        progress_bit_mask = sum(
            1 << item["bit"] for item in classes if item["progress"]
        )
        progress_mask_literal = f"{mask_width}'h{progress_bit_mask:x}"
        trigger_exprs = [
            _predicate_sv(item["predicate"], aliases)
            for item in classes
            if item["trigger"]
        ]
        trigger_expr = " || ".join(trigger_exprs) if trigger_exprs else "1'b0"
        qdepth = budget["qualified_ring_depth"]
        sdepth = budget["non_progress_ring_depth"]
        pdepth = max(1, budget["post_trigger_samples"])
        first_samples = budget["first_payload_samples"]
        no_progress = budget["no_progress_cycles"]
        chunks.extend(
            [
                f"module {module_name}(",
                ",\n".join(ports),
                ");",
                f"  localparam integer CODEX_Q_DEPTH = {qdepth};",
                f"  localparam integer CODEX_S_DEPTH = {sdepth};",
                f"  localparam integer CODEX_FIRST_SAMPLES = {first_samples};",
                f"  localparam longint unsigned CODEX_NO_PROGRESS = {no_progress};",
                "  integer codex_enabled;",
                "  integer codex_i;",
                "  longint unsigned codex_event_count;",
                "  longint unsigned codex_progress_count;",
                "  longint unsigned codex_state_count;",
                "  longint unsigned codex_first_time;",
                "  longint unsigned codex_last_time;",
                "  longint unsigned codex_last_progress_time;",
                "  longint unsigned codex_max_gap;",
                "  longint unsigned codex_idle_cycles;",
                "  logic codex_stall_emitted;",
                "  logic codex_triggered;",
                "  longint unsigned codex_post_count;",
                f"  logic [{mask_width - 1}:0] codex_sticky_mask;",
                f"  logic [{mask_width - 1}:0] codex_prev_state_mask;",
                f"  wire [{mask_width - 1}:0] class_mask_now = {{{', '.join(mask_expressions)}}};",
                f"  wire [{payload_width - 1}:0] payload_now = {payload_expr};",
                "  wire codex_payload_known = !$isunknown(payload_now);",
                f"  logic [{payload_width - 1}:0] codex_payload_xor;",
                f"  longint unsigned codex_class_count [0:{mask_width - 1}];",
                f"  longint unsigned codex_q_time [0:{qdepth - 1}];",
                f"  logic [{mask_width - 1}:0] codex_q_mask [0:{qdepth - 1}];",
                f"  logic [{payload_width - 1}:0] codex_q_payload [0:{qdepth - 1}];",
                f"  longint unsigned codex_s_time [0:{sdepth - 1}];",
                f"  logic [{mask_width - 1}:0] codex_s_mask [0:{sdepth - 1}];",
                f"  longint unsigned codex_p_time [0:{pdepth - 1}];",
                f"  logic [{mask_width - 1}:0] codex_p_mask [0:{pdepth - 1}];",
                f"  logic [{payload_width - 1}:0] codex_p_payload [0:{pdepth - 1}];",
                "  wire codex_stage_gate = " + gate_expr + ";",
                "  wire codex_progress_now = " + progress_expr + ";",
                "  wire codex_trigger_now = " + trigger_expr + ";",
                "  wire codex_state_change_now = "
                f"((class_mask_now & ~{progress_mask_literal}) != "
                f"(codex_prev_state_mask & ~{progress_mask_literal}));",
                "",
                "  initial begin",
                "    codex_enabled = $test$plusargs(\"CODEX_CAUSAL_OBSERVER\");",
                "    codex_event_count = 0; codex_progress_count = 0; codex_state_count = 0;",
                "    codex_first_time = 0; codex_last_time = 0; codex_last_progress_time = 0;",
                "    codex_max_gap = 0; codex_idle_cycles = 0; codex_stall_emitted = 0;",
                "    codex_triggered = 0; codex_post_count = 0;",
                "    codex_sticky_mask = '0; codex_prev_state_mask = '0; codex_payload_xor = '0;",
                f"    for (codex_i = 0; codex_i < {mask_width}; codex_i = codex_i + 1) codex_class_count[codex_i] = 0;",
                f"    if (codex_enabled) $display(\"CODEX_PROBE_V1 kind=ENABLED boundary={boundary_id} instance=%m\");",
                "  end",
                "",
                f"  always @(posedge {clock_alias}) begin",
                f"    if (!({reset_ok})) begin",
                "      codex_idle_cycles <= 0; codex_stall_emitted <= 0; codex_prev_state_mask <= '0;",
                "    end else if (codex_enabled && codex_stage_gate) begin",
                "      if (codex_progress_now || codex_state_change_now) begin",
                "        codex_event_count <= codex_event_count + 1;",
                "        codex_sticky_mask <= codex_sticky_mask | class_mask_now;",
                "        codex_prev_state_mask <= class_mask_now;",
                *["        " + line for line in class_counter_updates],
                "        if (codex_event_count == 0) codex_first_time <= $time;",
                "        codex_last_time <= $time;",
                "        if (codex_progress_now) begin",
                "          codex_progress_count <= codex_progress_count + 1;",
                "          if (codex_last_progress_time != 0 && ($time-codex_last_progress_time) > codex_max_gap)",
                "            codex_max_gap <= $time-codex_last_progress_time;",
                "          codex_last_progress_time <= $time; codex_idle_cycles <= 0; codex_stall_emitted <= 0;",
                "          codex_payload_xor <= codex_payload_xor ^ payload_now;",
                "          codex_q_time[codex_progress_count % CODEX_Q_DEPTH] <= $time;",
                "          codex_q_mask[codex_progress_count % CODEX_Q_DEPTH] <= class_mask_now;",
                "          codex_q_payload[codex_progress_count % CODEX_Q_DEPTH] <= payload_now;",
                "          if (codex_progress_count < CODEX_FIRST_SAMPLES)",
                f"            $display(\"CODEX_PROBE_V1 kind=EVENT boundary={boundary_id} instance=%m time=%0t mask=%0h payload=%0h payload_known=%0d payload_width={payload_width} seq=%0d\", $time, class_mask_now, payload_now, codex_payload_known, codex_progress_count);",
                "        end else begin",
                "          codex_state_count <= codex_state_count + 1;",
                "          codex_s_time[codex_state_count % CODEX_S_DEPTH] <= $time;",
                "          codex_s_mask[codex_state_count % CODEX_S_DEPTH] <= class_mask_now;",
                "        end",
                "        if (codex_trigger_now && !codex_triggered) begin",
                "          codex_triggered <= 1; codex_post_count <= 0;",
                f"          $display(\"CODEX_PROBE_V1 kind=TRIGGER boundary={boundary_id} instance=%m time=%0t mask=%0h payload=%0h payload_known=%0d payload_width={payload_width} seq=%0d\", $time, class_mask_now, payload_now, codex_payload_known, codex_event_count);",
                "        end",
                "      end else begin",
                "        codex_idle_cycles <= codex_idle_cycles + 1;",
                "        if (!codex_stall_emitted && codex_idle_cycles >= CODEX_NO_PROGRESS) begin",
                "          codex_stall_emitted <= 1;",
                f"          $display(\"CODEX_PROBE_V1 kind=STALL boundary={boundary_id} instance=%m time=%0t mask=%0h payload=0 seq=%0d\", $time, codex_sticky_mask, codex_progress_count);",
                "        end",
                "      end",
                f"      if (codex_triggered && codex_post_count < {budget['post_trigger_samples']}) begin",
                "        codex_p_time[codex_post_count] <= $time;",
                "        codex_p_mask[codex_post_count] <= class_mask_now;",
                "        codex_p_payload[codex_post_count] <= payload_now;",
                "        codex_post_count <= codex_post_count + 1;",
                "      end",
                "    end",
                "  end",
                "",
                "  final begin",
                "    if (codex_enabled) begin",
                f"      $display(\"CODEX_PROBE_V1 kind=SUMMARY boundary={boundary_id} instance=%m count=%0d state=%0d first=%0d last=%0d maxgap=%0d sticky=%0h xor=%0h\", codex_progress_count, codex_state_count, codex_first_time, codex_last_time, codex_max_gap, codex_sticky_mask, codex_payload_xor);",
                *["      " + line for line in class_final_lines],
                "      for (codex_i = 0; codex_i < CODEX_Q_DEPTH && codex_i < codex_progress_count; codex_i = codex_i + 1)",
                f"        $display(\"CODEX_PROBE_V1 kind=RING_PROGRESS boundary={boundary_id} instance=%m time=%0d mask=%0h payload=%0h payload_known=%0d payload_width={payload_width} seq=%0d\", codex_q_time[codex_i], codex_q_mask[codex_i], codex_q_payload[codex_i], !$isunknown(codex_q_payload[codex_i]), codex_i);",
                "      for (codex_i = 0; codex_i < CODEX_S_DEPTH && codex_i < codex_state_count; codex_i = codex_i + 1)",
                f"        $display(\"CODEX_PROBE_V1 kind=RING_STATE boundary={boundary_id} instance=%m time=%0d mask=%0h payload=0 seq=%0d\", codex_s_time[codex_i], codex_s_mask[codex_i], codex_i);",
                "      for (codex_i = 0; codex_i < codex_post_count; codex_i = codex_i + 1)",
                f"        $display(\"CODEX_PROBE_V1 kind=RING_POST boundary={boundary_id} instance=%m time=%0d mask=%0h payload=%0h payload_known=%0d payload_width={payload_width} seq=%0d\", codex_p_time[codex_i], codex_p_mask[codex_i], codex_p_payload[codex_i], !$isunknown(codex_p_payload[codex_i]), codex_i);",
                "    end",
                "  end",
                "endmodule",
                "",
                "`ifndef CODEX_SOURCE_BOUND_FOCUS",
                f"bind {boundary['target_module']} {module_name} {module_name}_inst (",
                ",\n".join(
                    f"    .{aliases[symbol_id]}({symbols[symbol_id]['name']})"
                    for symbol_id in symbol_ids
                ),
                ");",
                "`endif",
                "",
            ]
        )
    return "\n".join(chunks) + "\n"


def generate_focus_harness(catalog: dict[str, Any], plan: dict[str, Any]) -> str:
    symbols = {item["symbol_id"]: item for item in catalog["symbols"]}
    declarations: list[str] = []
    instances: list[str] = []
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        safe = _safe_identifier(boundary_id)
        module_name = f"codex_probe_{safe}"
        symbol_ids = _boundary_symbols(boundary)
        connections: list[str] = []
        for index, symbol_id in enumerate(symbol_ids):
            symbol = symbols[symbol_id]
            width = symbol["width_bits"]
            width_decl = "" if width == 1 else f"[{width - 1}:0] "
            local = f"focus_{safe}_p_{index}"
            declarations.append(f"  logic {width_decl}{local};")
            connections.append(f"    .p_{index}({local})")
        instances.extend(
            [
                f"  {module_name} focus_instance_{safe} (",
                ",\n".join(connections),
                "  );",
            ]
        )
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "`define CODEX_SOURCE_BOUND_FOCUS",
            "`include \"source_bound_causal_observer.svh\"",
            "module codex_source_bound_focus;",
            *declarations,
            *instances,
            "  initial begin #1 $finish; end",
            "endmodule",
            "",
        ]
    )


def generate_parser(plan: dict[str, Any]) -> str:
    embedded = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    return f'''#!/usr/bin/env python3
"""Generated exact CODEX_PROBE_V1 parser; do not hand edit."""
import argparse
import json
import re
from pathlib import Path

PLAN = json.loads({embedded!r})
STRICT = PLAN.get("schema") == "server-source-bound-probe-plan-v2"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/%+\\[\\]$-]+$")
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
PAYLOAD_KINDS = {{"EVENT", "TRIGGER", "RING_PROGRESS", "RING_POST"}}
BOUNDARY_MAP = {{item["boundary_id"]: item for item in PLAN["boundaries"]}}

def parse_line(line):
    if not line.startswith("CODEX_PROBE_V1 "):
        return None, None
    fields = {{}}
    for token in line.rstrip("\\n").split(" ")[1:]:
        if "=" not in token:
            return None, "malformed logger token"
        key, value = token.split("=", 1)
        if not key or not value or not TOKEN_RE.fullmatch(value):
            return None, "invalid logger token"
        if key in fields:
            return None, f"duplicate logger key: {{key}}"
        fields[key] = value
    required = {{"kind", "boundary", "instance"}}
    if not required.issubset(fields):
        return None, "logger record lacks identity"
    return fields, None

def in_scope(boundary, instance):
    if not STRICT:
        return True
    scope = boundary["instance_scope"]
    if scope["mode"] == "ALL_INSTANCES_KEYED":
        return True
    return instance in set(scope["expected_instances"])

def expected_keys(boundary_id):
    boundary = BOUNDARY_MAP[boundary_id]
    if not STRICT or boundary["instance_scope"]["mode"] == "ALL_INSTANCES_KEYED":
        return None
    return {{(boundary_id, item) for item in boundary["instance_scope"]["expected_instances"]}}

def validate_payload(fields, boundary, line_number, errors):
    if not STRICT or fields["kind"] not in PAYLOAD_KINDS:
        return True
    required = {{"payload", "payload_known", "payload_width", "seq"}}
    missing = sorted(required - set(fields))
    if missing:
        errors.append(f"line {{line_number}}: payload contract fields missing: {{missing}}")
        return False
    contract = boundary["payload_contract"]
    try:
        width = int(fields["payload_width"], 10)
    except ValueError:
        errors.append(f"line {{line_number}}: invalid payload width")
        return False
    if width != contract["width_bits"]:
        errors.append(
            f"line {{line_number}}: payload width {{width}} != {{contract['width_bits']}}"
        )
        return False
    if fields["payload_known"] != "1":
        errors.append(f"line {{line_number}}: payload is not binary-known")
        return False
    try:
        sequence = int(fields["seq"], 10)
    except ValueError:
        errors.append(f"line {{line_number}}: invalid payload sequence")
        return False
    if sequence < 0:
        errors.append(f"line {{line_number}}: negative payload sequence")
        return False
    if not HEX_RE.fullmatch(fields["payload"]):
        errors.append(f"line {{line_number}}: payload is not exact hexadecimal")
        return False
    try:
        value = int(fields["payload"], 16)
    except ValueError:
        errors.append(f"line {{line_number}}: payload numeric parse failed")
        return False
    if value >= (1 << width):
        errors.append(f"line {{line_number}}: payload exceeds declared width")
        return False
    return True

def evaluate(path, validated_log=None):
    errors = []
    summaries = {{}}
    sticky = {{}}
    live_event_count = {{}}
    enabled = set()
    raw_records = 0
    accepted_records = 0
    ignored_non_target_records = 0
    ignored_unknown_boundaries = 0
    observed_instances = {{}}
    seen_record_keys = set()
    validated_lines = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        fields, error = parse_line(line)
        if error:
            errors.append(f"line {{line_number}}: {{error}}")
            continue
        if fields is None:
            continue
        raw_records += 1
        boundary = fields["boundary"]
        boundary_spec = BOUNDARY_MAP.get(boundary)
        if boundary_spec is None:
            ignored_unknown_boundaries += 1
            continue
        instance = fields["instance"]
        observed_instances.setdefault(boundary, set()).add(instance)
        if not in_scope(boundary_spec, instance):
            ignored_non_target_records += 1
            continue
        if not validate_payload(fields, boundary_spec, line_number, errors):
            continue
        if STRICT and fields["kind"] in PAYLOAD_KINDS:
            record_key = (boundary, instance, fields["kind"], fields["seq"])
            if record_key in seen_record_keys:
                errors.append(f"line {{line_number}}: duplicate diagnostic record key")
                continue
            seen_record_keys.add(record_key)
        accepted_records += 1
        validated_lines.append(line)
        key = (boundary, instance)
        kind = fields["kind"]
        if kind == "ENABLED":
            enabled.add(key)
        if kind == "EVENT":
            live_event_count[key] = live_event_count.get(key, 0) + 1
        if "mask" in fields:
            try:
                sticky[key] = sticky.get(key, 0) | int(fields["mask"], 16)
            except ValueError:
                errors.append(f"line {{line_number}}: invalid hex mask")
        if kind == "SUMMARY":
            try:
                summaries[key] = {{
                    "count": int(fields["count"]),
                    "state": int(fields["state"]),
                    "sticky": int(fields["sticky"], 16),
                    "xor": fields["xor"],
                }}
                sticky[key] = sticky.get(key, 0) | summaries[key]["sticky"]
            except (KeyError, ValueError):
                errors.append(f"line {{line_number}}: malformed SUMMARY")
    if validated_log is not None:
        validated_log.parent.mkdir(parents=True, exist_ok=True)
        validated_log.write_text(
            "\\n".join(validated_lines) + ("\\n" if validated_lines else ""),
            encoding="utf-8",
        )
    observations = {{}}
    for observation in PLAN["decision_observations"]:
        boundary = observation["boundary_id"]
        metric = observation["metric"]
        keys = expected_keys(boundary)
        if keys is None:
            keys = {{key for key in set(summaries) | set(sticky) | set(live_event_count) | enabled if key[0] == boundary}}
        if metric == "summary_present":
            value = bool(keys) and all(key in summaries for key in keys)
        elif metric == "count_nonzero":
            value = bool(keys) and all(
                summaries.get(key, {{}}).get("count", live_event_count.get(key, 0)) > 0
                for key in keys
            )
        else:
            class_bit = next(item["bit"] for item in BOUNDARY_MAP[boundary]["classes"] if item["class_id"] == observation["class_id"])
            value = bool(keys) and all(bool(sticky.get(key, 0) & (1 << class_bit)) for key in keys)
        observations[observation["observation_id"]] = value
    raw_matches = [item for item in PLAN["candidates"] if item["signature"] == observations]
    missing_enable = []
    for boundary in PLAN["boundaries"]:
        boundary_id = boundary["boundary_id"]
        keys = expected_keys(boundary_id)
        if keys is None:
            if not any(key[0] == boundary_id for key in enabled):
                missing_enable.append(boundary_id)
        else:
            missing_enable.extend(
                f"{{key[0]}}@{{key[1]}}" for key in sorted(keys - enabled)
            )
    missing_summary = []
    for item in PLAN["decision_observations"]:
        if item["metric"] == "class_seen":
            continue
        boundary_id = item["boundary_id"]
        keys = expected_keys(boundary_id)
        if keys is None:
            present = any(
                key[0] == boundary_id and (key in summaries or live_event_count.get(key, 0) > 0)
                for key in set(summaries) | set(live_event_count)
            )
            if not present:
                missing_summary.append(boundary_id)
        else:
            missing_summary.extend(
                f"{{key[0]}}@{{key[1]}}"
                for key in sorted(keys)
                if key not in summaries and live_event_count.get(key, 0) == 0
            )
    if errors or missing_enable or missing_summary:
        decision = "EVIDENCE_INCOMPLETE"
        reason = "logger parse, enable, or required summary evidence is incomplete"
        matches = []
    elif len(raw_matches) == 1:
        matches = raw_matches
        decision = raw_matches[0]["root_cause_class"]
        reason = "exactly one candidate signature matches"
    elif len(raw_matches) > 1:
        matches = []
        decision = "EVIDENCE_INCOMPLETE"
        reason = "multiple candidate signatures match"
    else:
        matches = []
        decision = "EVIDENCE_INCOMPLETE"
        reason = "no declared candidate signature matches"
    enabled_receipt = [
        f"{{key[0]}}@{{key[1]}}" for key in sorted(enabled)
    ] if STRICT else sorted({{key[0] for key in enabled}})
    if STRICT:
        live_event_receipt = {{
            f"{{key[0]}}@{{key[1]}}": value
            for key, value in live_event_count.items()
        }}
    else:
        live_event_receipt = {{}}
        for (boundary_id, _instance), value in live_event_count.items():
            live_event_receipt[boundary_id] = (
                live_event_receipt.get(boundary_id, 0) + value
            )
    report = {{
        "schema": "server-source-bound-probe-decision-v2" if STRICT else "server-source-bound-probe-decision-v1",
        "decision": decision,
        "reason": reason,
        "matching_candidate_ids": [item["candidate_id"] for item in matches],
        "observations": observations,
        "candidate_match_count": len(matches),
        "missing_enabled_boundaries": missing_enable,
        "missing_required_summaries": missing_summary,
        "raw_record_count": raw_records,
        "accepted_target_record_count": accepted_records,
        "ignored_non_target_record_count": ignored_non_target_records,
        "ignored_unknown_boundary_record_count": ignored_unknown_boundaries,
        "observed_instances": {{key: sorted(value) for key, value in observed_instances.items()}},
        "live_event_count": live_event_receipt,
        "errors": errors,
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": "Generated observer evidence only; natural terminal, formal D and E4/E5 remain independent.",
    }}
    if STRICT:
        report["enabled_boundary_instances"] = enabled_receipt
        report["record_grouping_key"] = ["boundary_id", "canonical_instance", "seq"]
    else:
        report["enabled_boundaries"] = enabled_receipt
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validated-log", type=Path)
    args = parser.parse_args()
    report = evaluate(args.log, args.validated_log)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print(json.dumps({{"decision": report["decision"], "errors": len(report["errors"]), "output": str(args.output)}}, sort_keys=True))
    return 0 if report["decision"] != "EVIDENCE_INCOMPLETE" else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def diagnostic_semantics_sha256(
    catalog: dict[str, Any], plan: dict[str, Any]
) -> str:
    return semantic_sha256(
        {
            "schema": "server-diagnostic-semantics-fingerprint-v1",
            "plan_semantic_sha256": semantic_sha256(plan),
            "observer_sha256": sha256_bytes(generate_observer(catalog, plan).encode("utf-8")),
            "parser_sha256": sha256_bytes(generate_parser(plan).encode("utf-8")),
            "instance_scopes": {
                item["boundary_id"]: item.get("instance_scope")
                for item in plan.get("boundaries", [])
            },
            "payload_contracts": {
                item["boundary_id"]: item.get("payload_contract")
                for item in plan.get("boundaries", [])
            },
            "decision_observations": plan.get("decision_observations", []),
            "candidates": plan.get("candidates", []),
        }
    )


def _candidate_control_log(plan: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    """Build one exact, target-scoped logger trace for a declared signature."""
    observations = {
        item["observation_id"]: item for item in plan["decision_observations"]
    }
    signature = candidate["signature"]
    by_boundary: dict[str, list[dict[str, Any]]] = {}
    for observation_id, observation in observations.items():
        by_boundary.setdefault(observation["boundary_id"], []).append(
            {**observation, "expected": signature[observation_id]}
        )
    lines: list[str] = []
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        scope = boundary["instance_scope"]
        instances = scope["expected_instances"]
        boundary_observations = by_boundary.get(boundary_id, [])
        count_nonzero = any(
            item["metric"] == "count_nonzero" and item["expected"]
            for item in boundary_observations
        )
        sticky = 0
        for item in boundary_observations:
            if item["metric"] != "class_seen" or not item["expected"]:
                continue
            class_bit = next(
                entry["bit"]
                for entry in boundary["classes"]
                if entry["class_id"] == item["class_id"]
            )
            sticky |= 1 << class_bit
        width = boundary["payload_contract"]["width_bits"]
        for instance in instances:
            lines.append(
                f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary_id} instance={instance}"
            )
            if count_nonzero:
                lines.append(
                    "CODEX_PROBE_V1 "
                    f"kind=EVENT boundary={boundary_id} instance={instance} "
                    f"time=1 mask={sticky | 1:x} payload=0 seq=0 "
                    f"payload_known=1 payload_width={width}"
                )
            lines.append(
                "CODEX_PROBE_V1 "
                f"kind=SUMMARY boundary={boundary_id} instance={instance} "
                f"count={1 if count_nonzero else 0} state=0 first=0 last=0 "
                f"maxgap=0 sticky={sticky:x} xor=0"
            )
    return lines


def _run_exact_parser(
    parser_path: Path, log_lines: list[str], root: Path, case_id: str
) -> dict[str, Any]:
    log_path = root / f"{case_id}.log"
    output_path = root / f"{case_id}.json"
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(parser_path),
            "--log",
            str(log_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    decision: dict[str, Any] = {}
    if output_path.is_file():
        try:
            value = load_json(output_path)
            if isinstance(value, dict):
                decision = value
        except (OSError, json.JSONDecodeError):
            decision = {}
    report = {
        "case_id": case_id,
        "exit_code": result.returncode,
        "decision": decision.get("decision"),
        "matching_candidate_ids": decision.get("matching_candidate_ids", []),
        "parser_errors": decision.get("errors", []),
        "decision_report": decision,
        "stderr": result.stderr,
    }
    return report


def run_diagnostic_semantic_controls(
    catalog: dict[str, Any], plan: dict[str, Any], parser_bytes: bytes
) -> dict[str, Any]:
    """Exercise the exact final parser against positive and historical escapes."""
    errors: list[str] = []
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="codex_diag_semantics_") as temporary:
        root = Path(temporary)
        parser_path = root / "source_bound_causal_parser.py"
        parser_path.write_bytes(parser_bytes)
        positive_lines: list[str] | None = None
        for candidate in plan.get("candidates", []):
            lines = _candidate_control_log(plan, candidate)
            result = _run_exact_parser(
                parser_path, lines, root, f"positive_{candidate['candidate_id']}"
            )
            result["expected"] = candidate["root_cause_class"]
            result["control_class"] = "positive"
            result["pass"] = (
                result["exit_code"] == 0
                and result["decision"] == candidate["root_cause_class"]
                and result["matching_candidate_ids"] == [candidate["candidate_id"]]
            )
            if not result["pass"]:
                errors.append(
                    f"candidate positive control failed: {candidate['candidate_id']}"
                )
            cases.append(result)
            if positive_lines is None and any(
                observation["metric"] == "count_nonzero"
                and candidate["signature"][observation["observation_id"]]
                for observation in plan["decision_observations"]
            ):
                positive_lines = lines

        if positive_lines is None:
            errors.append("no candidate supplies a payload-bearing positive control")
        else:
            # Mutate the boundary that actually carries the selected positive
            # candidate's EVENT.  The first plan boundary may be an anchoring
            # boundary with no decision observation; mutating that boundary
            # would leave the decisive later instance untouched and let the
            # mixed wrong-instance regression escape.
            event_boundary_id = next(
                (
                    boundary["boundary_id"]
                    for boundary in plan["boundaries"]
                    if any(
                        "kind=EVENT" in line
                        and f"boundary={boundary['boundary_id']}" in line
                        for line in positive_lines
                    )
                ),
                None,
            )
            if event_boundary_id is None:
                errors.append("payload-bearing positive control has no decision EVENT boundary")
                first_boundary = plan["boundaries"][0]
            else:
                first_boundary = next(
                    boundary
                    for boundary in plan["boundaries"]
                    if boundary["boundary_id"] == event_boundary_id
                )
            target = first_boundary["instance_scope"]["expected_instances"][0]
            near_miss = first_boundary["instance_scope"]["near_miss_instances"][0]
            mutations: dict[str, list[str]] = {}
            mutations["v80_near_miss_instance_only"] = [
                line.replace(f"instance={target}", f"instance={near_miss}")
                if f"boundary={first_boundary['boundary_id']}" in line
                else line
                for line in positive_lines
            ]
            mixed = list(positive_lines)
            for index, line in enumerate(mixed):
                if (
                    f"boundary={first_boundary['boundary_id']}" in line
                    and "kind=ENABLED" not in line
                ):
                    mixed[index] = line.replace(
                        f"instance={target}", f"instance={near_miss}"
                    )
            mutations["v80_mixed_target_near_miss"] = mixed
            event_index = next(
                (index for index, line in enumerate(positive_lines) if "kind=EVENT" in line),
                None,
            )
            if event_index is None:
                errors.append("payload-bearing positive control lacks EVENT")
            else:
                for case_id, old, new in (
                    ("p34b_payload_x", "payload=0", "payload=x"),
                    ("p34b_payload_z", "payload=0", "payload=z"),
                    ("payload_known_zero", "payload_known=1", "payload_known=0"),
                    ("payload_width_wrong", "payload_width=", "payload_width=999"),
                ):
                    changed = list(positive_lines)
                    if case_id == "payload_width_wrong":
                        changed[event_index] = re.sub(
                            r"payload_width=[0-9]+", "payload_width=999", changed[event_index]
                        )
                    else:
                        changed[event_index] = changed[event_index].replace(old, new, 1)
                    mutations[case_id] = changed
                changed = list(positive_lines)
                changed[event_index] = re.sub(
                    r" payload=[^ ]+", "", changed[event_index]
                )
                mutations["payload_missing"] = changed
                changed = list(positive_lines)
                changed.insert(event_index + 1, changed[event_index])
                mutations["duplicate_boundary_instance_seq"] = changed

            for case_id, lines in mutations.items():
                result = _run_exact_parser(parser_path, lines, root, case_id)
                result["expected"] = "EVIDENCE_INCOMPLETE"
                result["control_class"] = "negative"
                result["pass"] = (
                    result["exit_code"] != 0
                    and result["decision"] == "EVIDENCE_INCOMPLETE"
                    and result["matching_candidate_ids"] == []
                )
                if not result["pass"]:
                    errors.append(f"historical negative control escaped: {case_id}")
                cases.append(result)
    return {
        "schema": "server-diagnostic-semantic-controls-v1",
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "diagnostic_semantics_sha256": diagnostic_semantics_sha256(catalog, plan),
        "case_count": len(cases),
        "positive_count": sum(item["control_class"] == "positive" for item in cases),
        "negative_count": sum(item["control_class"] == "negative" for item in cases),
        "cases": cases,
        "historical_regressions": [
            "serialized Conv v80 wrong-instance cross-aggregation",
            "native Conv p34b unknown X/Z payload parsed as numeric sentinel",
        ],
        "claim_boundary": "Exact package-local diagnostic parser semantics only.",
    }


def make_binding(
    catalog: dict[str, Any],
    plan: dict[str, Any],
    catalog_bytes: bytes,
    plan_bytes: bytes,
) -> dict[str, Any]:
    symbols = {item["symbol_id"]: item for item in catalog["symbols"]}
    return {
        "schema": (
            "server-source-bound-probe-binding-v2"
            if plan.get("schema") == "server-source-bound-probe-plan-v2"
            else "server-source-bound-probe-binding-v1"
        ),
        "diagnostic_semantics_sha256": diagnostic_semantics_sha256(catalog, plan),
        "catalog": {
            "path": "catalog.json",
            "bytes": len(catalog_bytes),
            "sha256": sha256_bytes(catalog_bytes),
        },
        "plan": {
            "path": "plan.json",
            "bytes": len(plan_bytes),
            "sha256": sha256_bytes(plan_bytes),
        },
        "rtl_tree_sha256": catalog["rtl_identity"]["rtl_tree_sha256"],
        "boundaries": [
            {
                "boundary_id": boundary["boundary_id"],
                "target_module": boundary["target_module"],
                "symbol_bindings": [
                    symbols[item] for item in _boundary_symbols(boundary)
                ],
                "logger_format": "CODEX_PROBE_V1 exact-key-value-v1",
                "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
                "qualified_and_state_rings_separate": True,
                "instance_scope": boundary.get("instance_scope"),
                "payload_contract": boundary.get("payload_contract"),
            }
            for boundary in plan["boundaries"]
        ],
        "free_form_hdl_identifiers_accepted": False,
        "private_hierarchical_xmr_generated": False,
        "claim_boundary": "Package-local read-only observer binding only.",
    }


def _safe_zip_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and value != "."


def validate_final_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    receipts: dict[str, Any] = {}
    duplicate_members: list[str] = []
    unsafe_members: list[str] = []
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            duplicate_members = sorted(
                key for key, value in Counter(names).items() if value > 1
            )
            unsafe_members = sorted(name for name in names if not _safe_zip_relative(name))
            if duplicate_members:
                errors.append(f"duplicate ZIP members: {duplicate_members}")
            if unsafe_members:
                errors.append(f"unsafe ZIP members: {unsafe_members}")
            if not duplicate_members and not unsafe_members:
                files = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"ZIP is unreadable: {exc}")

    contract_matches = sorted(
        name
        for name in files
        if name.endswith("/diagnostics/source_bound_final_zip_contract.json")
    )
    if len(contract_matches) != 1:
        errors.append(
            "exactly one diagnostics/source_bound_final_zip_contract.json is required"
        )
        contract = {}
        package_root = ""
    else:
        contract_member = contract_matches[0]
        package_root = contract_member[: -len("diagnostics/source_bound_final_zip_contract.json")]
        try:
            contract = json.loads(files[contract_member].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"final ZIP contract is invalid: {exc}")
            contract = {}
    if contract.get("schema") != "server-source-bound-final-zip-contract-v1":
        errors.append("final ZIP contract schema mismatch")
    if contract.get("rule_id") != "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001":
        errors.append("final ZIP contract rule mismatch")
    if contract.get("enforcement") != "required_next_fresh":
        errors.append("final ZIP source-bound enforcement mismatch")
    members = contract.get("members")
    if not isinstance(members, dict):
        errors.append("final ZIP contract members are missing")
        members = {}
    required_keys = {
        "catalog",
        "plan",
        "observer",
        "parser",
        "binding",
        "generation_report",
        "runner",
    }
    missing_keys = sorted(required_keys - set(members))
    extra_keys = sorted(set(members) - required_keys)
    if missing_keys:
        errors.append(f"final ZIP contract member keys missing: {missing_keys}")
    if extra_keys:
        errors.append(f"final ZIP contract member keys unexpected: {extra_keys}")
    member_bytes: dict[str, bytes] = {}
    for key in sorted(required_keys):
        relative = members.get(key)
        if not _safe_zip_relative(relative):
            errors.append(f"final ZIP contract path is unsafe: {key}={relative}")
            continue
        full = package_root + relative
        data = files.get(full)
        if data is None:
            errors.append(f"final ZIP required member is missing: {key}={full}")
            continue
        member_bytes[key] = data
        receipts[key] = {
            "path": full,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }

    catalog: dict[str, Any] = {}
    plan: dict[str, Any] = {}
    for key, target in (("catalog", "catalog"), ("plan", "plan")):
        if key not in member_bytes:
            continue
        try:
            value = json.loads(member_bytes[key].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"final ZIP {key} is invalid JSON: {exc}")
            continue
        if target == "catalog":
            catalog = value
        else:
            plan = value
    contract_validation = validate_contract(catalog, plan) if catalog and plan else {
        "valid": False,
        "errors": ["catalog/plan unavailable"],
        "warnings": [],
        "indistinguishable_candidate_pairs": [],
    }
    errors.extend(
        f"source-bound contract: {message}"
        for message in contract_validation.get("errors", [])
    )

    exact_generation: dict[str, Any] = {}
    semantic_controls: dict[str, Any] = {
        "schema": "server-diagnostic-semantic-controls-v1",
        "pass": False,
        "errors": ["strict semantic controls were not applicable"],
        "all_errors_collected": True,
        "diagnostic_semantics_sha256": None,
        "case_count": 0,
        "positive_count": 0,
        "negative_count": 0,
        "cases": [],
        "historical_regressions": [],
        "claim_boundary": "Exact package-local diagnostic parser semantics only.",
    }
    if contract_validation.get("valid"):
        expected = {
            "observer": generate_observer(catalog, plan).encode("utf-8"),
            "parser": generate_parser(plan).encode("utf-8"),
            "binding": pretty_json_bytes(
                make_binding(catalog, plan, member_bytes["catalog"], member_bytes["plan"])
            ),
        }
        for key, expected_bytes in expected.items():
            actual = member_bytes.get(key)
            equal = actual == expected_bytes
            exact_generation[key] = {
                "expected_sha256": sha256_bytes(expected_bytes),
                "actual_sha256": sha256_bytes(actual) if actual is not None else None,
                "byte_equal": equal,
            }
            if not equal:
                errors.append(f"final ZIP {key} differs from source-bound generation")
        if plan.get("schema") == "server-source-bound-probe-plan-v2":
            semantic_controls = run_diagnostic_semantic_controls(
                catalog, plan, member_bytes["parser"]
            )
            errors.extend(
                f"diagnostic semantic control: {message}"
                for message in semantic_controls["errors"]
            )

    generation_report: dict[str, Any] = {}
    if "generation_report" in member_bytes:
        try:
            generation_report = json.loads(
                member_bytes["generation_report"].decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"generation report is invalid JSON: {exc}")
        if generation_report.get("pass") is not True:
            errors.append("generation report did not pass")
        if generation_report.get("focused_syntax", {}).get("pass") is not True:
            errors.append("generated focused syntax did not pass")
        if plan.get("schema") == "server-source-bound-probe-plan-v2":
            expected_fingerprint = diagnostic_semantics_sha256(catalog, plan)
            if generation_report.get("diagnostic_semantics_sha256") != expected_fingerprint:
                errors.append(
                    "generation report diagnostic semantics fingerprint mismatch"
                )
        artifact_by_name = {
            Path(item.get("path", "")).name: item
            for item in generation_report.get("generated_artifacts", [])
            if isinstance(item, dict)
        }
        for key, filename in (
            ("observer", "source_bound_causal_observer.svh"),
            ("parser", "source_bound_causal_parser.py"),
            ("binding", "source_bound_probe_binding.json"),
        ):
            artifact = artifact_by_name.get(filename, {})
            actual = receipts.get(key, {})
            if artifact.get("sha256") != actual.get("sha256"):
                errors.append(f"generation report SHA does not bind final {key}")

    runner = ""
    if "runner" in member_bytes:
        try:
            runner = member_bytes["runner"].decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"runner is not UTF-8: {exc}")
    fixed_tokens = {
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
    }
    runner_checks: dict[str, bool] = {}
    for field, expected in fixed_tokens.items():
        declared = contract.get(field)
        if declared != expected:
            errors.append(f"final ZIP contract {field} must be {expected}")
        present = expected in runner
        runner_checks[field] = present
        if not present:
            errors.append(f"runner lacks required source-bound token: {expected}")

    report = {
        "schema": (
            "server-source-bound-final-zip-validation-v2"
            if plan.get("schema") == "server-source-bound-probe-plan-v2"
            else "server-source-bound-final-zip-validation-v1"
        ),
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "zip": file_receipt(zip_path),
        "pass": not errors,
        "errors": errors,
        "warnings": contract_validation.get("warnings", []),
        "all_errors_collected": True,
        "duplicate_members": duplicate_members,
        "unsafe_members": unsafe_members,
        "package_root": package_root.rstrip("/"),
        "member_receipts": receipts,
        "contract_validation": {
            key: value
            for key, value in contract_validation.items()
            if key not in {"errors", "warnings"}
        },
        "exact_generation": exact_generation,
        "runner_checks": runner_checks,
        "claim_boundary": (
            "Exact final ZIP source-bound observer/parser/binding and runner token "
            "closure only; production compile, simulation, natural terminal, formal D and E4/E5 remain independent."
        ),
    }
    if plan.get("schema") == "server-source-bound-probe-plan-v2":
        report["diagnostic_semantics_sha256"] = (
            diagnostic_semantics_sha256(catalog, plan)
            if contract_validation.get("valid")
            else None
        )
        report["plan_schema"] = plan.get("schema")
        report["semantic_controls"] = semantic_controls
    return report


def materialize(
    catalog_path: Path,
    plan_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    catalog_path = catalog_path.resolve()
    plan_path = plan_path.resolve()
    output_dir = output_dir.resolve()
    catalog = load_json(catalog_path)
    plan = load_json(plan_path)
    validation = validate_contract(catalog, plan)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    focused_syntax: dict[str, Any] = {
        "tool": "iverilog",
        "available": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "pass": False,
    }
    if validation["valid"]:
        observer_path = output_dir / "source_bound_causal_observer.svh"
        parser_path = output_dir / "source_bound_causal_parser.py"
        binding_path = output_dir / "source_bound_probe_binding.json"
        focus_path = output_dir / "source_bound_observer_focus.sv"
        observer_path.write_text(generate_observer(catalog, plan), encoding="utf-8", newline="\n")
        parser_path.write_text(generate_parser(plan), encoding="utf-8", newline="\n")
        focus_path.write_text(generate_focus_harness(catalog, plan), encoding="utf-8", newline="\n")
        symbols = {item["symbol_id"]: item for item in catalog["symbols"]}
        catalog_raw = catalog_path.read_bytes()
        plan_raw = plan_path.read_bytes()
        binding = make_binding(catalog, plan, catalog_raw, plan_raw)
        write_json(binding_path, binding)
        iverilog = shutil.which("iverilog")
        if iverilog is None:
            validation["errors"].append("iverilog is unavailable for generated exact-source focused syntax")
            validation["valid"] = False
        else:
            binary_path = output_dir / ".source_bound_focus.out"
            command = [
                iverilog,
                "-g2012",
                "-s",
                "codex_source_bound_focus",
                "-o",
                str(binary_path),
                str(focus_path),
            ]
            result = subprocess.run(
                command,
                cwd=output_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            focused_syntax = {
                "tool": "iverilog",
                "available": True,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "pass": result.returncode == 0,
            }
            if binary_path.exists():
                binary_path.unlink()
            if result.returncode != 0:
                validation["errors"].append(
                    "generated exact-source focused syntax failed: "
                    + result.stderr.strip()[:4000]
                )
                validation["valid"] = False
        artifacts = [
            file_receipt(path, output_dir)
            for path in (observer_path, parser_path, binding_path, focus_path)
        ]
    report = {
        "schema": (
            "server-source-bound-observer-generation-report-v2"
            if plan.get("schema") == "server-source-bound-probe-plan-v2"
            else "server-source-bound-observer-generation-report-v1"
        ),
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "pass": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "all_errors_collected": True,
        "catalog": file_receipt(catalog_path),
        "plan": file_receipt(plan_path),
        "contract": {
            key: value
            for key, value in validation.items()
            if key not in (
                {"errors", "warnings", "valid"}
                | (
                    set()
                    if plan.get("schema") == "server-source-bound-probe-plan-v2"
                    else {"strict_diagnostic_semantics", "instance_scoped_boundary_count"}
                )
            )
        },
        "generated_artifacts": artifacts,
        "focused_syntax": focused_syntax,
        "runtime_contract": {
            "profile": plan.get("profile"),
            "observer_plusarg": "+CODEX_CAUSAL_OBSERVER",
            "always_on_summaries": True,
            "separate_qualified_and_non_progress_rings": True,
            "multiclass_bitmap_no_loss": True,
            "per_cycle_text_logging": False,
            "full_waveform_default": False,
            "slowdown_limit_hard": False,
            "same_workload_ab_calibration_required": True,
        },
        "package_action": "NONE",
        "server_action": "NONE",
        "claim_boundary": (
            "Local generated diagnostic source and decision-matrix closure only; "
            "production compile, simulation, natural terminal, formal D and E4/E5 remain independent."
        ),
    }
    if plan.get("schema") == "server-source-bound-probe-plan-v2":
        report["diagnostic_semantics_sha256"] = (
            diagnostic_semantics_sha256(catalog, plan)
            if validation["valid"]
            else None
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    catalog_parser = sub.add_parser("catalog")
    catalog_parser.add_argument("--rtl-root", type=Path, required=True)
    catalog_parser.add_argument("--rtl-tree-sha256", required=True)
    catalog_parser.add_argument("--source", type=Path, action="append", required=True)
    catalog_parser.add_argument("--output", type=Path, required=True)

    materialize_parser = sub.add_parser("materialize")
    materialize_parser.add_argument("--catalog", type=Path, required=True)
    materialize_parser.add_argument("--plan", type=Path, required=True)
    materialize_parser.add_argument("--output-dir", type=Path, required=True)
    materialize_parser.add_argument("--report", type=Path, required=True)
    materialize_parser.add_argument("--cheap-check-output", type=Path)
    final_zip_parser = sub.add_parser("validate-final-zip")
    final_zip_parser.add_argument("--zip", type=Path, required=True)
    final_zip_parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "catalog":
        report = build_catalog(args.rtl_root, args.source, args.rtl_tree_sha256)
        write_json(args.output, report)
        print(json.dumps({"valid": report["valid"], "symbols": report["symbol_count"], "errors": len(report["errors"]), "output": str(args.output)}, sort_keys=True))
        return 0 if report["valid"] else 1

    if args.command == "validate-final-zip":
        report = validate_final_zip(args.zip.resolve())
        write_json(args.report.resolve(), report)
        print(
            json.dumps(
                {
                    "pass": report["pass"],
                    "errors": len(report["errors"]),
                    "report": str(args.report.resolve()),
                },
                sort_keys=True,
            )
        )
        return 0 if report["pass"] else 1

    report = materialize(args.catalog, args.plan, args.output_dir)
    write_json(args.report, report)
    if args.cheap_check_output:
        write_json(
            args.cheap_check_output,
            {
                "schema": "server-package-cheap-check-result-v1",
                "gate_id": "source_bound_observer_generation",
                "pass": report["pass"],
                "errors": report["errors"],
                "warnings": report["warnings"],
            },
        )
    print(json.dumps({"pass": report["pass"], "errors": len(report["errors"]), "warnings": len(report["warnings"]), "report": str(args.report)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
