#!/usr/bin/env python3
"""Bind the actual production VCS command and node0004 ACK source identity.

The tool is read-only with respect to the server RTL tree.  It copies exact
source bytes into the package-owned attempt evidence directory and derives a
source-level driver exact set bound to the successful production elaboration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Any


TARGET_REL = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
TOP_FILELIST_REL = "rtl/filelists/NDP_Top_phy_filelist.f"
PARAMETER_REL = "rtl/includes/NDP_Parameters.svh"
ACK_NAME = "mse_buf_queue_bp_pre"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.is_file(),
        **(
            {"bytes": path.stat().st_size, "sha256": sha(path)}
            if path.is_file()
            else {}
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def expand_env(value: str) -> str:
    return os.path.expandvars(value.replace("${MC_DIR}", os.environ.get("MC_DIR", "${MC_DIR}")))


def find_vcs_command(log: str) -> tuple[str | None, list[str]]:
    candidates: list[str] = []
    for line in log.splitlines():
        stripped = line.strip()
        if re.match(r"^(?:\S*/)?vcs(?:\s|$)", stripped) and " -full64" in f" {stripped}":
            candidates.append(stripped)
    if not candidates:
        return None, []
    command = candidates[-1]
    try:
        return command, shlex.split(command, posix=True)
    except ValueError:
        return command, command.split()


def parse_filelist(
    path: Path,
    *,
    compile_cwd: Path,
    seen: set[Path],
    filelists: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> None:
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    filelists.append(identity(resolved))
    if not resolved.is_file():
        return
    tokens: list[str] = []
    for raw in resolved.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        try:
            tokens.extend(shlex.split(line, posix=True))
        except ValueError:
            tokens.extend(line.split())
    index = 0
    while index < len(tokens):
        token = expand_env(tokens[index])
        if token in {"-F", "-f"} and index + 1 < len(tokens):
            nested_raw = expand_env(tokens[index + 1])
            base = resolved.parent if token == "-F" else compile_cwd
            nested = Path(nested_raw)
            if not nested.is_absolute():
                nested = base / nested
            parse_filelist(
                nested,
                compile_cwd=compile_cwd,
                seen=seen,
                filelists=filelists,
                sources=sources,
            )
            index += 2
            continue
        if token.startswith("+incdir+") or token.startswith("+") or token.startswith("-"):
            index += 1
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = resolved.parent / candidate
        if candidate.suffix.lower() in {".v", ".sv", ".vp", ".vhd", ".vhdl"}:
            sources.append(identity(candidate.resolve()))
        index += 1


def compile_tokens(argv: list[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    filelists: list[str] = []
    includes: list[str] = []
    defines: list[str] = []
    parameters: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"-F", "-f"} and index + 1 < len(argv):
            filelists.append(argv[index + 1])
            index += 2
            continue
        if token.startswith("+incdir+"):
            includes.extend(item for item in token[len("+incdir+") :].split("+") if item)
        elif token.startswith("+define+"):
            defines.append(token[len("+define+") :])
        elif token.startswith("-pvalue+") or token.startswith("-parameter"):
            parameters.append(token)
        index += 1
    return filelists, includes, defines, parameters


def macro_map(header: str, command_defines: list[str]) -> dict[str, str]:
    macros: dict[str, str] = {}
    logical = re.sub(r"\\\r?\n", "", header)
    for match in re.finditer(r"(?m)^\s*`define\s+([A-Za-z_][A-Za-z0-9_]*)\s+([^\r\n/]+)", logical):
        macros[match.group(1)] = match.group(2).strip()
    for item in command_defines:
        name, separator, value = item.partition("=")
        macros[name] = value if separator else "1"
    return macros


def preprocess_target(source: str, macros: dict[str, str]) -> tuple[str, list[str], list[str]]:
    source = re.sub(r"(?m)^\s*`include\s+\"NDP_Parameters\.svh\"\s*$", "", source)
    used = sorted(set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)", source)))
    unresolved: set[str] = set()

    def expand_name(name: str, stack: tuple[str, ...] = ()) -> str:
        if name in stack or name not in macros:
            unresolved.add(name)
            return "`" + name
        value = macros[name]
        return re.sub(
            r"`([A-Za-z_][A-Za-z0-9_]*)",
            lambda match: expand_name(match.group(1), stack + (name,)),
            value,
        )

    expanded = re.sub(
        r"`([A-Za-z_][A-Za-z0-9_]*)", lambda match: expand_name(match.group(1)), source
    )
    return expanded, used, sorted(unresolved)


def strip_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/", "", re.sub(r"//.*", "", source), flags=re.S)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--compile-log", type=Path, required=True)
    parser.add_argument("--compile-exit", type=Path, required=True)
    parser.add_argument("--target-instance", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.server_root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = args.compile_log.read_text(encoding="utf-8", errors="replace") if args.compile_log.is_file() else ""
    command, argv = find_vcs_command(log)
    raw_filelists, raw_includes, defines, parameter_overrides = compile_tokens(argv)
    target = root / TARGET_REL
    top_filelist = root / TOP_FILELIST_REL
    parameter_header = root / PARAMETER_REL
    compile_exit = int(args.compile_exit.read_text().strip()) if args.compile_exit.is_file() else 125

    actual_vcs = {
        "schema": "server-actual-vcs-argv-v1",
        "cwd": str(root),
        "command_from_production_compile_log": command,
        "argv": argv,
        "filelist_tokens": raw_filelists,
        "include_tokens": raw_includes,
        "define_tokens": defines,
        "parameter_override_tokens": parameter_overrides,
        "compile_exit": compile_exit,
    }
    write_json(out / "actual_vcs_argv.json", actual_vcs)

    closure_filelists: list[dict[str, Any]] = []
    closure_sources: list[dict[str, Any]] = []
    seen: set[Path] = set()
    selected_filelist = top_filelist
    if raw_filelists:
        candidate = Path(expand_env(raw_filelists[0]))
        selected_filelist = candidate if candidate.is_absolute() else root / candidate
    parse_filelist(
        selected_filelist,
        compile_cwd=root,
        seen=seen,
        filelists=closure_filelists,
        sources=closure_sources,
    )

    copies = {
        "actual_top_filelist.f": selected_filelist,
        "actual_target_source.sv": target,
        "actual_parameter_header.svh": parameter_header,
    }
    for name, source_path in copies.items():
        if source_path.is_file():
            shutil.copyfile(source_path, out / name)

    source_text = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    header_text = parameter_header.read_text(encoding="utf-8", errors="replace") if parameter_header.is_file() else ""
    macros = macro_map(header_text, defines)
    preprocessed, used_macros, unresolved = preprocess_target(source_text, macros)
    preprocessed_path = out / "preprocessed_target.sv"
    preprocessed_path.write_text(preprocessed, encoding="utf-8", newline="\n")
    preprocess_receipt = {
        "schema": "server-target-preprocess-receipt-v1",
        "method": "ACTUAL_SOURCE_EXACT_INCLUDE_PLUS_OBJECT_MACRO_EXPANSION",
        "source": identity(target),
        "include": identity(parameter_header),
        "actual_compile_defines": defines,
        "used_macros": used_macros,
        "resolved_values": {name: macros.get(name) for name in used_macros},
        "unresolved_macros": unresolved,
        "complete_for_target_object_macros": not unresolved,
        "output": identity(preprocessed_path),
        "claim_boundary": "Package-local deterministic preprocessing of the actual server source; not a vendor compiler AST dump.",
    }
    write_json(out / "preprocessed_target_receipt.json", preprocess_receipt)

    active = strip_comments(source_text)
    driver_matches = list(
        re.finditer(
            rf"assign\s+{ACK_NAME}\s*\[\s*([^]]+)\s*\]\s*=\s*(.*?);",
            active,
            flags=re.S,
        )
    )
    lane_count_text = macros.get("MSE_BQ_INPORT_NUM", "2")
    lane_match = re.search(r"\d+", lane_count_text)
    lane_count = int(lane_match.group()) if lane_match else 2
    elaboration_markers = [
        marker
        for marker in (
            "Verdi KDB elaboration finished with 0 error(s)",
            "Verdi KDB elaboration done",
            "Compilation completed!",
        )
        if marker in log
    ]
    driver_set = {
        "schema": "server-elaborated-ack-driver-set-v1",
        "target_instance": args.target_instance,
        "net": ACK_NAME,
        "width": lane_count,
        "production_compile_exit": compile_exit,
        "production_elaboration_markers": elaboration_markers,
        "production_elaboration_succeeded": compile_exit == 0,
        "method": "ACTUAL_COMPILED_SOURCE_DRIVER_SCAN_BOUND_TO_SUCCESSFUL_PRODUCTION_ELABORATION",
        "vendor_interactive_driver_query": False,
        "driver_templates": [
            {
                "generate_index": match.group(1).strip(),
                "equation": " ".join(match.group(2).split()),
                "source_offset": match.start(),
            }
            for match in driver_matches
        ],
        "expanded_driver_exact_set": [
            {
                "hierarchical_net": f"{args.target_instance}.{ACK_NAME}[{lane}]",
                "source": str(target),
                "equation": " ".join(driver_matches[0].group(2).split()) if driver_matches else None,
            }
            for lane in range(lane_count)
        ],
        "multiple_or_force_tokens_in_target": sorted(
            set(re.findall(rf"\b(?:force|release|tran|alias)\b[^;]*{ACK_NAME}[^;]*", active))
        ),
        "exact_set_complete": len(driver_matches) == 1 and lane_count == 2,
        "claim_boundary": (
            "Exact actual-source driver templates and lane expansion bound to a successful production elaboration; "
            "no vendor interactive driver-cone API was available to this package."
        ),
    }
    write_json(out / "elaborated_ack_driver_set.json", driver_set)

    target_resolved = target.resolve()
    target_in_closure = any(
        Path(item["path"]).resolve() == target_resolved and item.get("exists") is True
        for item in closure_sources
    )
    errors: list[str] = []
    if command is None:
        errors.append("actual production VCS command absent from compile log")
    if not target.is_file() or not parameter_header.is_file() or not selected_filelist.is_file():
        errors.append("target/filelist/include source absent")
    if not target_in_closure:
        errors.append("target is absent from recursively resolved production filelist closure")
    if unresolved:
        errors.append(f"unresolved target macros: {unresolved}")
    if not driver_set["exact_set_complete"]:
        errors.append("ACK driver source exact set is not one two-lane generate template")
    report = {
        "schema": "server-compile-source-identity-v2",
        "status": "COMPLETE" if not errors else "EVIDENCE_INCOMPLETE",
        "compile_cwd": str(root),
        "compile_exit": compile_exit,
        "actual_vcs_argv": identity(out / "actual_vcs_argv.json"),
        "selected_makefile": identity(root / "Makefile.tb_NDP_Top_new_phy"),
        "selected_top_filelist": identity(selected_filelist),
        "recursive_filelists": closure_filelists,
        "recursive_source_count": len(closure_sources),
        "recursive_source_identity_sha256": hashlib.sha256(
            json.dumps(closure_sources, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "target_in_filelist_closure": target_in_closure,
        "actual_target_source": identity(target),
        "actual_parameter_header": identity(parameter_header),
        "compile_includes": raw_includes,
        "compile_defines": defines,
        "compile_parameter_overrides": parameter_overrides,
        "preprocessed_target_receipt": identity(out / "preprocessed_target_receipt.json"),
        "elaborated_ack_driver_set": identity(out / "elaborated_ack_driver_set.json"),
        "package_local_observers": [
            identity(args.package_root / "tb_probe/source_bound_causal_observer.svh"),
            identity(args.package_root / "tb_probe/buffer_ack_phase_observer.svh"),
            identity(args.package_root / "tb_probe/buffer_ack_portable_query_observer.svh"),
        ],
        "errors": errors,
        "claim_boundary": (
            "Actual production command/filelist/include/define/parameter/source identity and deterministic target preprocessing; "
            "interactive vendor driver-cone interrogation remains explicitly distinguished."
        ),
    }
    write_json(args.output, report)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
