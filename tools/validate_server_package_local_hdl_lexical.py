#!/usr/bin/env python3
"""Fail closed on reserved SystemVerilog identifiers in a tree or final ZIP.

This is a deliberately cheap companion to the existing focused/full HDL
frontend gate.  It scans a staging tree before expensive packaging and then
recomputes the same result from the exact final archive bytes.  It aggregates
every declaration-name violation before returning.  It does not claim scope,
elaboration, XMR validity, or production VCS equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "server-package-local-hdl-lexical-validation-v1"
RULE_ID = "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
HDL_SUFFIXES = {".sv", ".svh", ".v", ".vh"}

# IEEE 1800 keywords plus the legacy Verilog keyword set.  A keyword is legal
# as syntax but never as a simple declaration identifier.  Escaped identifiers
# (for example ``\\sequence ``) are intentionally not rejected.
RESERVED = frozenset(
    """
accept_on alias always always_comb always_ff always_latch and assert assign
assume automatic before begin bind bins binsof bit break buf bufif0 bufif1
byte case casex casez cell chandle checker class clocking cmos config const
constraint context continue cover covergroup coverpoint cross deassign default
defparam design disable dist do edge else end endchecker endclass endclocking
endconfig endfunction endgenerate endgroup endinterface endmodule endpackage
endprimitive endprogram endproperty endspecify endsequence endtable endtask
enum event eventually expect export extends extern final first_match for force
foreach forever fork forkjoin function generate genvar global highz0 highz1 if
iff ifnone ignore_bins illegal_bins implements implies import incdir include
initial inout input inside instance int integer interconnect intersect interface
join join_any join_none large let liblist library local localparam logic longint
macromodule matches medium modport module nand negedge nettype new nexttime nmos
nor noshowcancelled not notif0 notif1 null or output package packed parameter
pmos posedge primitive priority program property protected pull0 pull1 pulldown
pullup pulsestyle_ondetect pulsestyle_onevent pure rand randc randcase randsequence
rcmos real realtime ref reg reject_on release repeat restrict return rnmos rpmos
rtran rtranif0 rtranif1 s_always s_eventually s_nexttime s_until s_until_with
scalared sequence shortint shortreal showcancelled signed small solve specify
specparam static string strong strong0 strong1 struct super supply0 supply1 sync_accept_on
sync_reject_on table tagged task this throughout time timeprecision timeunit tran
tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef union unique
unique0 unsigned until until_with untyped use uwire var vectored virtual void
wait wait_order wand weak weak0 weak1 while wildcard wire with within wor xnor
xor
""".split()
)

TYPE_HEADS = (
    "integer|int|logic|reg|wire|bit|byte|shortint|longint|time|realtime|"
    "event|genvar|real|shortreal|string|chandle"
)
DECLARATION = re.compile(rf"\b(?P<type>{TYPE_HEADS})\b(?P<body>[^;]*);", re.S)
PORT_DECLARATION = re.compile(r"\b(?:input|output|inout|ref)\b(?P<body>[^;]*);", re.S)
NAMED_CONSTRUCT = re.compile(
    r"\b(?:module|interface|program|package|class|checker|covergroup|property|"
    r"sequence|primitive|config)\b\s+(?:(?:automatic|static)\s+)?"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
)
WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
MODIFIERS = {"signed", "unsigned", "automatic", "static", "const", "var", "rand", "randc"}


class LexicalGateError(ValueError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _safe_zip(archive: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    infos = archive.infolist()
    if not infos:
        raise LexicalGateError("ZIP is empty")
    names = [item.filename for item in infos]
    if len(names) != len(set(names)):
        raise LexicalGateError("ZIP contains duplicate member names")
    roots: set[str] = set()
    for info in infos:
        name = info.filename
        if "\\" in name:
            raise LexicalGateError(f"ZIP member contains backslash: {name}")
        posix = PurePosixPath(name)
        if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
            raise LexicalGateError(f"unsafe ZIP member: {name}")
        roots.add(posix.parts[0])
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise LexicalGateError(f"ZIP member is a symlink: {name}")
    if len(roots) != 1:
        raise LexicalGateError(f"ZIP must have one top-level root: {sorted(roots)}")
    return next(iter(roots)), infos


def _strip_noncode(text: str) -> str:
    """Replace comments, strings and escaped identifiers while preserving lines."""
    out: list[str] = []
    index = 0
    state = "code"
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                out.extend("  ")
                index += 2
                state = "line"
                continue
            if char == "/" and nxt == "*":
                out.extend("  ")
                index += 2
                state = "block"
                continue
            if char == '"':
                out.append(" ")
                index += 1
                state = "string"
                continue
            if char == "\\":
                out.append(" ")
                index += 1
                state = "escaped_identifier"
                continue
            out.append(char)
            index += 1
            continue
        if state == "line":
            out.append("\n" if char == "\n" else " ")
            index += 1
            if char == "\n":
                state = "code"
            continue
        if state == "block":
            if char == "*" and nxt == "/":
                out.extend("  ")
                index += 2
                state = "code"
            else:
                out.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if state == "string":
            if char == "\\" and nxt:
                out.extend("  ")
                index += 2
            elif char == '"':
                out.append(" ")
                index += 1
                state = "code"
            else:
                out.append("\n" if char == "\n" else " ")
                index += 1
            continue
        # Escaped identifiers terminate at whitespace and are legal even when
        # their spelling is a reserved word.
        if char.isspace():
            out.append(char)
            index += 1
            state = "code"
        else:
            out.append(" ")
            index += 1
    return "".join(out)


def _split_declarators(body: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    start = 0
    depth = 0
    for index, char in enumerate(body):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            rows.append((body[start:index], start))
            start = index + 1
    rows.append((body[start:], start))
    return rows


def _declaration_names(body: str, body_offset: int) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for fragment, relative in _split_declarators(body):
        before_assignment = fragment.split("=", 1)[0]
        without_ranges = re.sub(r"\[[^\]]*\]", " ", before_assignment)
        words = list(WORD.finditer(without_ranges))
        candidates = [item for item in words if item.group(0) not in MODIFIERS]
        if not candidates:
            continue
        candidate = candidates[-1]
        found.append((candidate.group(0), body_offset + relative + candidate.start()))
    return found


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_hdl(text: str, member: str) -> list[dict[str, Any]]:
    code = _strip_noncode(text)
    violations: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()

    def add(name: str, offset: int, role: str) -> None:
        if name not in RESERVED or (offset, name) in seen:
            return
        seen.add((offset, name))
        line = _line_number(code, offset)
        source_line = text.splitlines()[line - 1] if line <= len(text.splitlines()) else ""
        violations.append(
            {
                "member": member,
                "line": line,
                "identifier": name,
                "role": role,
                "source_excerpt": source_line.strip()[:240],
            }
        )

    for match in DECLARATION.finditer(code):
        for name, offset in _declaration_names(match.group("body"), match.start("body")):
            add(name, offset, "data_declaration")
    for match in PORT_DECLARATION.finditer(code):
        for name, offset in _declaration_names(match.group("body"), match.start("body")):
            add(name, offset, "port_declaration")
    for match in NAMED_CONSTRUCT.finditer(code):
        add(match.group("name"), match.start("name"), "named_construct")
    return violations


def _finish_report(
    *,
    input_kind: str,
    input_path: Path,
    input_sha: str | None,
    root: str | None,
    members: list[dict[str, Any]],
    violations: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    violations.sort(key=lambda row: (row["member"], row["line"], row["identifier"]))
    if violations:
        errors.append(f"reserved SystemVerilog declaration identifiers: {len(violations)}")
    return {
        "schema": SCHEMA,
        "rule_id": RULE_ID,
        "input": {
            "kind": input_kind,
            "path": str(input_path),
            "sha256": input_sha,
            "root": root,
        },
        "applicable": bool(members),
        "hdl_member_count": len(members),
        "hdl_members": members,
        "reserved_identifier_violations": violations,
        "all_errors_collected": True,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Reserved-identifier lexical guard only; existing focused/full frontend, scope/name-resolution, state ownership and production compile gates remain required.",
    }


def _scan_bytes(
    data: bytes,
    member: str,
    members: list[dict[str, Any]],
    violations: list[dict[str, Any]],
    errors: list[str],
) -> None:
    digest = hashlib.sha256(data).hexdigest()
    members.append({"path": member, "bytes": len(data), "sha256": digest})
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        errors.append(f"HDL member is not UTF-8: {member}: {error}")
        return
    violations.extend(scan_hdl(text, member))


def validate_tree(tree_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    root: str | None = None
    tree_sha: str | None = None
    try:
        resolved = tree_path.resolve(strict=True)
        if not resolved.is_dir() or tree_path.is_symlink():
            raise LexicalGateError("staging tree must be a real directory")
        root = resolved.name
        for path in sorted(resolved.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise LexicalGateError(f"staging tree contains symlink: {path}")
            if not path.is_file() or path.suffix.lower() not in HDL_SUFFIXES:
                continue
            relative = path.relative_to(resolved).as_posix()
            _scan_bytes(path.read_bytes(), relative, members, violations, errors)
        identity = "\n".join(
            f'{item["path"]}\t{item["bytes"]}\t{item["sha256"]}' for item in members
        )
        tree_sha = hashlib.sha256((identity + "\n").encode("utf-8")).hexdigest()
    except (OSError, LexicalGateError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return _finish_report(
        input_kind="tree",
        input_path=tree_path,
        input_sha=tree_sha,
        root=root,
        members=members,
        violations=violations,
        errors=errors,
    )


def validate_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    root: str | None = None
    zip_sha: str | None = None
    try:
        zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        with zipfile.ZipFile(zip_path) as archive:
            root, infos = _safe_zip(archive)
            for info in infos:
                if info.is_dir() or PurePosixPath(info.filename).suffix.lower() not in HDL_SUFFIXES:
                    continue
                data = archive.read(info)
                _scan_bytes(data, info.filename, members, violations, errors)
    except (OSError, zipfile.BadZipFile, LexicalGateError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return _finish_report(
        input_kind="zip",
        input_path=zip_path,
        input_sha=zip_sha,
        root=root,
        members=members,
        violations=violations,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tree", dest="tree_path", type=Path)
    source.add_argument("--zip", dest="zip_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_tree(args.tree_path) if args.tree_path else validate_zip(args.zip_path)
    _write_json(args.output, report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
