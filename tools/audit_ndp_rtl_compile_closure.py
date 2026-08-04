#!/usr/bin/env python3
"""Flatten and audit the active NDP_Top RTL filelist without changing RTL.

The repository filelists use VCS ``-F`` nesting and environment variables that
Icarus does not consume directly.  This tool resolves that control-plane syntax,
emits Icarus-compatible flattened filelists, and creates one diagnostic source
copy containing only the explicitly authorized first-error edit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


SOURCE_SUFFIXES = {".v", ".sv", ".vp", ".vlib"}
MODULE_RE = re.compile(r"(?m)^\s*module\s+(?:automatic\s+)?([A-Za-z_]\w*)\b")
INCLUDE_RE = re.compile(r'(?m)^\s*`include\s+"([^"]+)"')
CONFLICT_RE = re.compile(r"(?m)^(<<<<<<<|=======|>>>>>>>)")
ENV_RE = re.compile(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def expand_env(value: str, env: dict[str, str], unresolved: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        if name not in env:
            unresolved.add(name)
            return match.group(0)
        return env[name]

    return ENV_RE.sub(replace, value)


@dataclass
class Closure:
    root: Path
    env: dict[str, str]
    filelists: list[Path] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)
    include_dirs: list[Path] = field(default_factory=list)
    missing_sources: list[dict[str, object]] = field(default_factory=list)
    missing_filelists: list[dict[str, object]] = field(default_factory=list)
    unresolved_env: set[str] = field(default_factory=set)
    skipped_options: list[dict[str, object]] = field(default_factory=list)
    _seen_filelists: set[Path] = field(default_factory=set)
    _seen_sources: set[Path] = field(default_factory=set)
    _seen_include_dirs: set[Path] = field(default_factory=set)

    def _resolve(self, raw: str, base: Path) -> Path | None:
        expanded = expand_env(raw.strip().strip('"').strip("'"), self.env, self.unresolved_env)
        if "$" in expanded:
            return None
        candidate = Path(expanded)
        if not candidate.is_absolute():
            candidate = base / candidate
        return candidate.resolve()

    def add_source(self, raw: str, base: Path, origin: Path, line: int) -> None:
        source = self._resolve(raw, base)
        if source is None or not source.is_file():
            self.missing_sources.append(
                {"origin": rel(origin, self.root), "line": line, "raw": raw}
            )
            return
        if source not in self._seen_sources:
            self._seen_sources.add(source)
            self.sources.append(source)

    def add_include_dir(self, raw: str, base: Path, origin: Path, line: int) -> None:
        directory = self._resolve(raw, base)
        if directory is None or not directory.is_dir():
            self.skipped_options.append(
                {
                    "kind": "missing_or_unresolved_include_dir",
                    "origin": rel(origin, self.root),
                    "line": line,
                    "raw": raw,
                }
            )
            return
        if directory not in self._seen_include_dirs:
            self._seen_include_dirs.add(directory)
            self.include_dirs.append(directory)

    def parse_filelist(self, path: Path) -> None:
        path = path.resolve()
        if path in self._seen_filelists:
            return
        self._seen_filelists.add(path)
        if not path.is_file():
            self.missing_filelists.append({"raw": str(path)})
            return
        self.filelists.append(path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        index = 0
        while index < len(lines):
            raw_line = lines[index]
            line_number = index + 1
            index += 1
            while raw_line.rstrip().endswith("\\") and index < len(lines):
                raw_line = raw_line.rstrip()[:-1] + " " + lines[index].strip()
                index += 1
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            stripped = stripped.split("//", 1)[0].strip()
            tokens = stripped.split()
            token_index = 0
            while token_index < len(tokens):
                token = tokens[token_index]
                token_index += 1
                if token in {"-F", "-f"}:
                    if token_index >= len(tokens):
                        self.missing_filelists.append(
                            {
                                "origin": rel(path, self.root),
                                "line": line_number,
                                "raw": token,
                            }
                        )
                        continue
                    nested_raw = tokens[token_index]
                    token_index += 1
                    nested = self._resolve(nested_raw, path.parent)
                    if nested is None:
                        self.missing_filelists.append(
                            {
                                "origin": rel(path, self.root),
                                "line": line_number,
                                "raw": nested_raw,
                            }
                        )
                    else:
                        self.parse_filelist(nested)
                elif token.startswith("+incdir+"):
                    for directory in token[len("+incdir+") :].split("+"):
                        if directory:
                            self.add_include_dir(directory, path.parent, path, line_number)
                elif token.startswith("+libext+"):
                    self.skipped_options.append(
                        {
                            "kind": "vcs_library_extension_option",
                            "origin": rel(path, self.root),
                            "line": line_number,
                            "raw": token,
                        }
                    )
                elif token == "-v":
                    if token_index < len(tokens):
                        self.add_source(
                            tokens[token_index], path.parent, path, line_number
                        )
                        token_index += 1
                elif Path(token).suffix.lower() in SOURCE_SUFFIXES:
                    self.add_source(token, path.parent, path, line_number)
                else:
                    self.skipped_options.append(
                        {
                            "kind": "non_source_option",
                            "origin": rel(path, self.root),
                            "line": line_number,
                            "raw": token,
                        }
                    )


def write_flattened(
    path: Path,
    closure: Closure,
    replacements: dict[Path, Path] | None = None,
) -> None:
    replacements = replacements or {}
    lines = [f"+incdir+{directory.as_posix()}" for directory in closure.include_dirs]
    for source in closure.sources:
        emitted = replacements.get(source, source)
        lines.append(emitted.as_posix())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_filelist(
    iverilog: Path, filelist: Path, output: Path, log: Path
) -> dict[str, object]:
    command = [
        str(iverilog),
        "-g2012",
        "-Wall",
        "-s",
        "NDP_Top_new",
        "-f",
        str(filelist),
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=filelist.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.write_text(completed.stdout, encoding="utf-8")
    return {
        "command": command,
        "exit_code": completed.returncode,
        "log": log.name,
        "output_exists": output.is_file(),
    }


def scan_static(closure: Closure) -> dict[str, object]:
    module_defs: dict[str, list[dict[str, object]]] = defaultdict(list)
    conflicts: list[dict[str, object]] = []
    includes: list[dict[str, object]] = []
    include_dirs = [source.parent for source in closure.sources] + closure.include_dirs
    for source in closure.sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in MODULE_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            module_defs[match.group(1)].append(
                {"path": rel(source, closure.root), "line": line}
            )
        for match in CONFLICT_RE.finditer(text):
            conflicts.append(
                {
                    "path": rel(source, closure.root),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "marker": match.group(1),
                }
            )
        for match in INCLUDE_RE.finditer(text):
            include_name = match.group(1)
            resolved = next(
                (
                    candidate / include_name
                    for candidate in include_dirs
                    if (candidate / include_name).is_file()
                ),
                None,
            )
            includes.append(
                {
                    "path": rel(source, closure.root),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "include": include_name,
                    "resolved": rel(resolved, closure.root) if resolved else None,
                }
            )
    duplicates = {
        name: definitions
        for name, definitions in sorted(module_defs.items())
        if len(definitions) > 1
    }


def lower_map_arrays_for_iverilog(text: str) -> tuple[str, int]:
    """Lower four constant unpacked arrays unsupported by local Icarus."""

    names = ("LOW_PREV_MAP", "LOW_NEXT_MAP", "HIGH_PREV_MAP", "HIGH_NEXT_MAP")
    count = 0
    for name in names:
        pattern = re.compile(
            rf"(?m)^(?P<indent>\s*)localparam\s+int\s+{name}\s*\[0:27\]\s*"
            rf"=\s*'\{{(?P<values>[^}}]+)\}}\s*;"
        )
        match = pattern.search(text)
        if not match:
            continue
        values = [item.strip() for item in match.group("values").split(",")]
        if len(values) != 28:
            raise SystemExit(
                f"fail-closed: {name} expected 28 entries, got {len(values)}"
            )
        indent = match.group("indent")
        body = [
            f"{indent}function automatic integer {name}(input integer index);",
            f"{indent}    case (index)",
        ]
        body.extend(
            f"{indent}        {index}: {name} = {value};"
            for index, value in enumerate(values)
        )
        body.extend(
            [
                f"{indent}        default: {name} = 0;",
                f"{indent}    endcase",
                f"{indent}endfunction",
            ]
        )
        text = text[: match.start()] + "\n".join(body) + text[match.end() :]
        text = re.sub(rf"\b{name}\s*\[\s*SLICE_ID\s*\]", f"{name}(SLICE_ID)", text)
        count += 1
    return text, count


def lower_localparam_arrays_for_iverilog(text: str) -> tuple[str, int]:
    """Lower constant integer arrays to module-scope constant functions."""

    pattern = re.compile(
        r"(?m)^(?P<indent>\s*)localparam\s+int\s+(?P<name>[A-Za-z_]\w*)"
        r"\s*\[[^\]]+\]\s*=\s*'\{(?P<values>[^}]+)\}\s*;"
    )
    initial_matches = list(pattern.finditer(text))
    names = sorted({match.group("name") for match in initial_matches})
    functions: list[str] = []
    serial = 0
    for name in names:
        name_pattern = re.compile(
            rf"(?m)^(?P<indent>\s*)localparam\s+int\s+{name}"
            rf"\s*\[[^\]]+\]\s*=\s*'\{{(?P<values>[^}}]+)\}}\s*;"
        )
        matches = list(name_pattern.finditer(text))
        if not matches:
            continue
        chunks: list[str] = [text[: matches[0].start()]]
        for index, match in enumerate(matches):
            serial += 1
            function_name = f"__codex_iverilog_{name}_{serial}"
            values = [item.strip() for item in match.group("values").split(",")]
            function_lines = [
                f"function automatic integer {function_name}(input integer index);",
                "  case (index)",
            ]
            function_lines.extend(
                f"    {value_index}: {function_name} = {value};"
                for value_index, value in enumerate(values)
            )
            function_lines.extend(
                [
                    f"    default: {function_name} = 0;",
                    "  endcase",
                    "endfunction",
                ]
            )
            functions.append("\n".join(function_lines))
            chunks.append(
                f"{match.group('indent')}// Icarus compatibility lowering: {name}\n"
            )
            region_end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )
            region = text[match.end() : region_end]
            region = re.sub(
                rf"\b{name}\s*\[\s*([A-Za-z_]\w*)\s*\]",
                rf"{function_name}(\1)",
                region,
            )
            chunks.append(region)
        text = "".join(chunks)
    if functions:
        port_end = re.search(r"(?m)^\s*\);\s*$", text)
        if not port_end:
            raise SystemExit("fail-closed: module port-list close not found")
        insertion = "\n\n" + "\n\n".join(functions) + "\n"
        text = text[: port_end.end()] + insertion + text[port_end.end() :]
    return text, serial


def lower_live_signed_casts_for_iverilog(text: str) -> tuple[str, int]:
    lines: list[str] = []
    count = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("//"):
            lines.append(line)
            continue
        lowered, line_count = re.subn(
            r"\bsigned'\(([^()]+)\)", r"$signed(\1)", line
        )
        lines.append(lowered)
        count += line_count
    return "".join(lines), count
    return {
        "module_definition_count": sum(len(items) for items in module_defs.values()),
        "unique_module_count": len(module_defs),
        "duplicate_module_definitions": duplicates,
        "conflict_markers": conflicts,
        "includes": includes,
        "unresolved_includes": [item for item in includes if item["resolved"] is None],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--iverilog", type=Path, default=Path(r"C:\iverilog\bin\iverilog.exe")
    )
    args = parser.parse_args()

    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    mc_dir = root / "DDR_Model" / "MC_IP" / "rtl"
    closure = Closure(root=root, env={"MC_DIR": str(mc_dir)})
    top_filelist = root / "filelists" / "NDP_Top_filelist.f"
    closure.parse_filelist(top_filelist)

    known = (
        root
        / "Slice"
        / "Specialized_Array"
        / "SA_PE"
        / "SA_PE_ALU"
        / "SA_PE_Float_Control.v"
    ).resolve()
    diagnostic_copy = out / "diagnostic_fix1" / rel(known, root)
    diagnostic_copy.parent.mkdir(parents=True, exist_ok=True)
    original_text = known.read_text(encoding="utf-8", errors="strict")
    fixed_text, replacement_count = re.subn(
        r"(output\s*\[\s*1\s*:\s*0\s*\]\s*o_Config)\s*,(\s*\n\s*\);)",
        r"\1\2",
        original_text,
        count=1,
    )
    if replacement_count != 1:
        raise SystemExit("fail-closed: known trailing-comma edit did not match exactly once")
    diagnostic_copy.write_text(fixed_text, encoding="utf-8", newline="")

    protected = (
        root
        / "DDR_Model"
        / "MC_IP"
        / "test"
        / "mc_env"
        / "tb"
        / "quad"
        / "phy_dram_wrapper.vp"
    ).resolve()
    protected_copy = out / "diagnostic_compat" / rel(protected, root)
    protected_copy.parent.mkdir(parents=True, exist_ok=True)
    protected_text = protected.read_text(encoding="utf-8", errors="strict")
    protected_marker = protected_text.find("`protected128")
    if protected_marker < 0:
        raise SystemExit("fail-closed: protected128 marker not found")
    protected_stub_text = (
        protected_text[:protected_marker]
        + "assign rdrdy_n = 1'b0;\n"
        + "assign rdl = {DATA_WIDTH+CHECKBIT_WIDTH{1'b0}};\n"
        + "endmodule\n"
    )
    protected_copy.write_text(protected_stub_text, encoding="utf-8", newline="")

    top_source = (root / "NDP_Top.sv").resolve()
    top_copy = out / "diagnostic_compat" / rel(top_source, root)
    top_copy.parent.mkdir(parents=True, exist_ok=True)
    top_text = top_source.read_text(encoding="utf-8", errors="strict")
    lowered_top_text, lowered_map_count = lower_map_arrays_for_iverilog(top_text)
    if lowered_map_count != 4:
        raise SystemExit(
            f"fail-closed: expected four map arrays, lowered {lowered_map_count}"
        )
    top_copy.write_text(lowered_top_text, encoding="utf-8", newline="")

    array_sources = [
        (
            root
            / "Slice"
            / "General_Array"
            / "GA_PE_Group"
            / "GA_PE_Group_Interconnect.sv"
        ).resolve(),
        (
            root / "Slice" / "Index_Generation_Array" / "IGA_Interconnect.sv"
        ).resolve(),
    ]
    array_replacements: dict[Path, Path] = {}
    array_edit_records: list[dict[str, object]] = []
    for array_source in array_sources:
        array_text = array_source.read_text(encoding="utf-8", errors="strict")
        lowered_array_text, array_count = lower_localparam_arrays_for_iverilog(
            array_text
        )
        array_copy = out / "diagnostic_compat2" / rel(array_source, root)
        array_copy.parent.mkdir(parents=True, exist_ok=True)
        array_copy.write_text(lowered_array_text, encoding="utf-8", newline="")
        array_replacements[array_source] = array_copy
        array_edit_records.append(
            {
                "kind": "local_tool_compatibility_lowering_not_repair",
                "source": rel(array_source, root),
                "source_sha256": sha256(array_source),
                "copy": str(array_copy),
                "copy_sha256": sha256(array_copy),
                "replacement_count": array_count,
                "description": "lower constant unpacked localparam arrays to scoped constant functions for Icarus",
                "snapshot_modified": sha256(array_source)
                != hashlib.sha256(array_text.encode("utf-8")).hexdigest(),
            }
        )

    signed_source = (
        root
        / "Slice"
        / "Index_Generation_Array"
        / "IGA_LC"
        / "IGA_LC_Counter.sv"
    ).resolve()
    signed_text = signed_source.read_text(encoding="utf-8", errors="strict")
    signed_lowered_text, signed_count = lower_live_signed_casts_for_iverilog(
        signed_text
    )
    if signed_count != 5:
        raise SystemExit(
            f"fail-closed: expected five signed casts, lowered {signed_count}"
        )
    signed_copy = out / "diagnostic_compat2" / rel(signed_source, root)
    signed_copy.parent.mkdir(parents=True, exist_ok=True)
    signed_copy.write_text(signed_lowered_text, encoding="utf-8", newline="")

    original_filelist = out / "flattened_original.f"
    fixed_filelist = out / "flattened_fix1.f"
    compat_filelist = out / "flattened_fix1_compat.f"
    compat2_filelist = out / "flattened_fix1_compat2.f"
    write_flattened(original_filelist, closure)
    write_flattened(fixed_filelist, closure, {known: diagnostic_copy})
    write_flattened(
        compat_filelist,
        closure,
        {
            known: diagnostic_copy,
            protected: protected_copy,
            top_source: top_copy,
        },
    )
    compat2_replacements = {
        known: diagnostic_copy,
        protected: protected_copy,
        top_source: top_copy,
        signed_source: signed_copy,
        **array_replacements,
    }
    write_flattened(compat2_filelist, closure, compat2_replacements)
    static = scan_static(closure)

    original_compile = compile_filelist(
        args.iverilog,
        original_filelist,
        out / "original.vvp",
        out / "original_normalized_compile.log",
    )
    fix1_compile = compile_filelist(
        args.iverilog,
        fixed_filelist,
        out / "fix1.vvp",
        out / "fix1_compile.log",
    )
    compat_compile = compile_filelist(
        args.iverilog,
        compat_filelist,
        out / "fix1_compat.vvp",
        out / "fix1_compat_compile.log",
    )
    compat2_compile = compile_filelist(
        args.iverilog,
        compat2_filelist,
        out / "fix1_compat2.vvp",
        out / "fix1_compat2_compile.log",
    )

    manifest = {
        "schema": "ndp_rtl_active_compile_closure_audit_v1",
        "snapshot_root": str(root),
        "top_filelist": rel(top_filelist, root),
        "top_module": "NDP_Top_new",
        "environment_bindings": {"MC_DIR": rel(mc_dir, root)},
        "unresolved_environment_variables": sorted(closure.unresolved_env),
        "counts": {
            "filelists": len(closure.filelists),
            "sources": len(closure.sources),
            "include_dirs": len(closure.include_dirs),
        },
        "filelists": [rel(path, root) for path in closure.filelists],
        "sources": [
            {"path": rel(path, root), "sha256": sha256(path)}
            for path in closure.sources
        ],
        "include_dirs": [rel(path, root) for path in closure.include_dirs],
        "missing_sources": closure.missing_sources,
        "missing_filelists": closure.missing_filelists,
        "skipped_options": closure.skipped_options,
        "diagnostic_edits": [
            {
                "kind": "candidate_repair",
                "source": rel(known, root),
                "source_sha256": sha256(known),
                "copy": str(diagnostic_copy),
                "copy_sha256": sha256(diagnostic_copy),
                "replacement_count": replacement_count,
                "description": "remove comma after o_Config immediately before ANSI port-list close",
                "snapshot_modified": sha256(known)
                != hashlib.sha256(original_text.encode("utf-8")).hexdigest(),
            },
            {
                "kind": "local_tool_compatibility_stub_not_repair",
                "source": rel(protected, root),
                "source_sha256": sha256(protected),
                "copy": str(protected_copy),
                "copy_sha256": sha256(protected_copy),
                "description": "retain module interface and replace VCS protected128 body with constant outputs",
                "snapshot_modified": sha256(protected)
                != hashlib.sha256(protected_text.encode("utf-8")).hexdigest(),
            },
            {
                "kind": "local_tool_compatibility_lowering_not_repair",
                "source": rel(top_source, root),
                "source_sha256": sha256(top_source),
                "copy": str(top_copy),
                "copy_sha256": sha256(top_copy),
                "replacement_count": lowered_map_count,
                "description": "lower four constant unpacked localparam maps to constant functions for Icarus",
                "snapshot_modified": sha256(top_source)
                != hashlib.sha256(top_text.encode("utf-8")).hexdigest(),
            },
            *array_edit_records,
            {
                "kind": "local_tool_compatibility_lowering_not_repair",
                "source": rel(signed_source, root),
                "source_sha256": sha256(signed_source),
                "copy": str(signed_copy),
                "copy_sha256": sha256(signed_copy),
                "replacement_count": signed_count,
                "description": "lower SystemVerilog signed type casts to Icarus $signed calls",
                "snapshot_modified": sha256(signed_source)
                != hashlib.sha256(signed_text.encode("utf-8")).hexdigest(),
            },
        ],
        "static_scan": static,
        "compile": {
            "original": original_compile,
            "fix1": fix1_compile,
            "fix1_compat": compat_compile,
            "fix1_compat2": compat2_compile,
        },
    }
    manifest_path = out / "active_closure_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    print(
        json.dumps(
            {
                "original_exit": original_compile["exit_code"],
                "fix1_exit": fix1_compile["exit_code"],
                "fix1_compat_exit": compat_compile["exit_code"],
                "fix1_compat2_exit": compat2_compile["exit_code"],
                "manifest": str(manifest_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
